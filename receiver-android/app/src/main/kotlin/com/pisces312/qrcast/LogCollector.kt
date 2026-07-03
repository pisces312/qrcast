package com.pisces312.qrcast

import android.content.Context
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 双轨日志收集器：内存缓冲区 + 外部文件
 * 文件写入异步化：通过 ArrayBlockingQueue + 后台消费者线程，
 * 避免在 cameraExecutor 等线程上阻塞 IO。
 */
object LogCollector {

    private const val TAG = "QRCast"
    private const val MAX_MEMORY_LOGS = 500
    private const val MAX_LOG_FILE_SIZE = 1 * 1024 * 1024L // 1MB
    private const val LOG_FILE_NAME = "app_logs.txt"
    private const val CRASH_LOG_FILE_NAME = "crash_logs.txt"

    private val memoryLogs = ConcurrentLinkedQueue<LogEntry>()
    private var fileLogger: File? = null
    private val dateFormat = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.getDefault())

    // Async file writing
    private val writeQueue = java.util.concurrent.ArrayBlockingQueue<String>(2048)
    private val writerRunning = AtomicBoolean(false)
    private var writerThread: Thread? = null

    data class LogEntry(
        val timestamp: Long,
        val level: String,
        val tag: String,
        val message: String
    ) {
        fun format(): String {
            return "${dateFormat.format(Date(timestamp))} [$level/$tag] $message"
        }
    }

    fun init(context: Context) {
        val logDir = File(context.getExternalFilesDir(null), "logs").apply { mkdirs() }
        fileLogger = File(logDir, LOG_FILE_NAME)
        startWriterThread()
        log("INFO", TAG, "LogCollector initialized")
    }

    private fun startWriterThread() {
        if (writerRunning.getAndSet(true)) return
        writerThread = Thread({
            while (writerRunning.get() || writeQueue.isNotEmpty()) {
                try {
                    val line = writeQueue.poll(100, java.util.concurrent.TimeUnit.MILLISECONDS)
                    if (line != null) {
                        writeLineToFile(line)
                    }
                } catch (_: InterruptedException) {
                    break
                }
            }
            writerRunning.set(false)
        }, "LogWriter")
        writerThread?.isDaemon = true
        writerThread?.start()
    }

    private fun writeLineToFile(line: String) {
        fileLogger?.let { file ->
            try {
                if (file.length() > MAX_LOG_FILE_SIZE) {
                    trimLogFile(file)
                }
                file.appendText(line + "\n")
            } catch (_: Exception) {
            }
        }
    }

    fun log(level: String, tag: String, message: String) {
        val entry = LogEntry(System.currentTimeMillis(), level, tag, message)

        memoryLogs.offer(entry)
        if (memoryLogs.size > MAX_MEMORY_LOGS) {
            memoryLogs.poll()
        }

        // Enqueue for async file write
        writeQueue.offer(entry.format())

        when (level) {
            "ERROR" -> Log.e(tag, message)
            "WARN" -> Log.w(tag, message)
            "INFO" -> Log.i(tag, message)
            "DEBUG" -> Log.d(tag, message)
            else -> Log.v(tag, message)
        }
    }

    fun d(tag: String, message: String) = log("DEBUG", tag, message)
    fun i(tag: String, message: String) = log("INFO", tag, message)
    fun w(tag: String, message: String) = log("WARN", tag, message)
    fun e(tag: String, message: String) = log("ERROR", tag, message)
    fun e(tag: String, message: String, throwable: Throwable) {
        log("ERROR", tag, "$message\n${throwable.stackTraceToString()}")
    }

    private fun trimLogFile(file: File) {
        try {
            val lines = file.readLines()
            if (lines.size > 100) {
                file.writeText(lines.takeLast(lines.size / 2).joinToString("\n", postfix = "\n"))
            } else {
                file.writeText("")
            }
        } catch (_: Exception) {
            file.writeText("")
        }
    }

    fun getMemoryLogs(): List<LogEntry> = memoryLogs.toList()

    fun getFileLogs(): String {
        return try {
            fileLogger?.readText() ?: ""
        } catch (e: Exception) {
            "读取日志文件失败: ${e.message}"
        }
    }

    fun clearLogs() {
        memoryLogs.clear()
        fileLogger?.let {
            try {
                it.writeText("")
            } catch (_: Exception) {
            }
        }
    }

    fun shutdown() {
        writerRunning.set(false)
        writerThread?.interrupt()
    }
}
