package com.lanvoicechat.app

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.io.EOFException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : AppCompatActivity() {

    private val sampleRate = 16000
    private val channels = 1
    private val frameMs = 10
    private val blockSamples = sampleRate * frameMs / 1000
    private val frameBytes = blockSamples * 2

    private val msgJoin: Byte = 1
    private val msgAudio: Byte = 2
    private val msgLeave: Byte = 3
    private val msgSys: Byte = 4

    private lateinit var hostInput: EditText
    private lateinit var portInput: EditText
    private lateinit var roomInput: EditText
    private lateinit var nameInput: EditText
    private lateinit var connectBtn: Button
    private lateinit var muteBtn: Button
    private lateinit var disconnectBtn: Button
    private lateinit var statusText: TextView
    private lateinit var logText: TextView

    private var socket: Socket? = null
    private var inputStream: InputStream? = null
    private var outputStream: OutputStream? = null
    private var recorder: AudioRecord? = null
    private var player: AudioTrack? = null

    private val running = AtomicBoolean(false)
    private val muted = AtomicBoolean(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        bindViews()
        ensurePermissions()

        connectBtn.setOnClickListener { connect() }
        disconnectBtn.setOnClickListener { disconnect() }
        muteBtn.setOnClickListener { toggleMute() }

        appendLog("请输入服务端参数后点击连接")
    }

    override fun onDestroy() {
        disconnect()
        super.onDestroy()
    }

    private fun bindViews() {
        hostInput = findViewById(R.id.hostInput)
        portInput = findViewById(R.id.portInput)
        roomInput = findViewById(R.id.roomInput)
        nameInput = findViewById(R.id.nameInput)
        connectBtn = findViewById(R.id.connectBtn)
        muteBtn = findViewById(R.id.muteBtn)
        disconnectBtn = findViewById(R.id.disconnectBtn)
        statusText = findViewById(R.id.statusText)
        logText = findViewById(R.id.logText)
    }

    private fun ensurePermissions() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 1001)
        }
    }

    private fun setUiConnected(connected: Boolean) {
        runOnUiThread {
            connectBtn.isEnabled = !connected
            disconnectBtn.isEnabled = connected
            muteBtn.isEnabled = connected
            if (!connected) {
                muteBtn.text = "静音"
                muted.set(false)
                statusText.text = "状态：未连接"
            } else {
                statusText.text = "状态：已连接（低延迟）"
            }
        }
    }

    private fun appendLog(msg: String) {
        runOnUiThread {
            logText.append(msg + "\n")
        }
    }

    private fun connect() {
        val host = hostInput.text.toString().trim()
        val room = roomInput.text.toString().trim()
        val name = nameInput.text.toString().trim().ifEmpty { "android-user" }
        val port = portInput.text.toString().trim().toIntOrNull()

        if (host.isEmpty() || room.isEmpty() || port == null) {
            appendLog("参数错误：请检查 IP/端口/房间")
            return
        }

        appendLog("正在连接 $host:$port ...")

        Thread {
            try {
                val sock = Socket()
                sock.tcpNoDelay = true
                sock.connect(InetSocketAddress(host, port), 4000)
                socket = sock
                inputStream = sock.getInputStream()
                outputStream = sock.getOutputStream()

                sendPacket(msgJoin, JSONObject(mapOf("room" to room, "name" to name)).toString().toByteArray(Charsets.UTF_8))
                setupAudio()
                running.set(true)

                Thread { captureLoop() }.start()
                Thread { recvLoop() }.start()

                setUiConnected(true)
                appendLog("连接成功")
            } catch (e: Exception) {
                appendLog("连接失败: ${e.message}")
                disconnect()
            }
        }.start()
    }

    private fun setupAudio() {
        val minIn = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        val inBuffer = maxOf(minIn, frameBytes * 4)

        recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            inBuffer
        )

        val minOut = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        val outBuffer = maxOf(minOut, frameBytes * 6)

        player = AudioTrack(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build(),
            AudioFormat.Builder()
                .setSampleRate(sampleRate)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .build(),
            outBuffer,
            AudioTrack.MODE_STREAM,
            AudioManager.AUDIO_SESSION_ID_GENERATE
        )

        recorder?.startRecording()
        player?.play()
    }

    private fun captureLoop() {
        val localRecorder = recorder ?: return
        val frame = ByteArray(frameBytes)

        while (running.get()) {
            val read = localRecorder.read(frame, 0, frame.size, AudioRecord.READ_BLOCKING)
            if (read == frameBytes && !muted.get()) {
                try {
                    sendPacket(msgAudio, frame)
                } catch (_: Exception) {
                    break
                }
            }
        }
    }

    private fun recvLoop() {
        try {
            while (running.get()) {
                val packet = recvPacket() ?: break
                val type = packet.first
                val payload = packet.second

                if (type == msgAudio) {
                    if (payload.size == frameBytes) {
                        player?.write(payload, 0, payload.size, AudioTrack.WRITE_NON_BLOCKING)
                    }
                } else if (type == msgSys) {
                    val rawText = payload.toString(Charsets.UTF_8)
                    val text = try {
                        JSONObject(rawText).optString("text", rawText)
                    } catch (_: Exception) {
                        rawText
                    }
                    appendLog("[系统] $text")
                }
            }
        } catch (_: Exception) {
        } finally {
            disconnect()
        }
    }

    private fun toggleMute() {
        val nowMuted = !muted.get()
        muted.set(nowMuted)
        muteBtn.text = if (nowMuted) "取消静音" else "静音"
        appendLog(if (nowMuted) "麦克风已静音" else "麦克风已开启")
    }

    private fun disconnect() {
        if (!running.getAndSet(false)) {
            setUiConnected(false)
        }

        try {
            sendPacket(msgLeave, ByteArray(0))
        } catch (_: Exception) {
        }

        try {
            recorder?.stop()
        } catch (_: Exception) {
        }
        try {
            recorder?.release()
        } catch (_: Exception) {
        }
        recorder = null

        try {
            player?.stop()
        } catch (_: Exception) {
        }
        try {
            player?.release()
        } catch (_: Exception) {
        }
        player = null

        try {
            inputStream?.close()
        } catch (_: Exception) {
        }
        inputStream = null

        try {
            outputStream?.close()
        } catch (_: Exception) {
        }
        outputStream = null

        try {
            socket?.close()
        } catch (_: Exception) {
        }
        socket = null

        setUiConnected(false)
        appendLog("已断开")
    }

    private fun sendPacket(type: Byte, payload: ByteArray) {
        val out = outputStream ?: throw IllegalStateException("not connected")
        val header = ByteBuffer.allocate(5)
            .order(ByteOrder.BIG_ENDIAN)
            .put(type)
            .putInt(payload.size)
            .array()
        synchronized(out) {
            out.write(header)
            if (payload.isNotEmpty()) {
                out.write(payload)
            }
            out.flush()
        }
    }

    private fun recvPacket(): Pair<Byte, ByteArray>? {
        val input = inputStream ?: return null
        val header = readExact(input, 5) ?: return null
        val type = header[0]
        val size = ByteBuffer.wrap(header, 1, 4).order(ByteOrder.BIG_ENDIAN).int
        if (size < 0 || size > 2_000_000) {
            throw IllegalStateException("invalid packet size: $size")
        }
        val payload = if (size == 0) ByteArray(0) else readExact(input, size) ?: return null
        return Pair(type, payload)
    }

    private fun readExact(input: InputStream, n: Int): ByteArray? {
        val result = ByteArray(n)
        var offset = 0
        while (offset < n) {
            val read = input.read(result, offset, n - offset)
            if (read < 0) {
                if (offset == 0) return null
                throw EOFException("stream closed")
            }
            offset += read
        }
        return result
    }
}
