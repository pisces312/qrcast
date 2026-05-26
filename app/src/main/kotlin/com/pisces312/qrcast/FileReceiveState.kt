package com.pisces312.qrcast

import java.util.concurrent.ConcurrentHashMap

class FileReceiveState(
    val fileKey: String,
    var fileName: String? = null,
    var fileCrc32: Long? = null,
    var fileSize: Long? = null,
    var isCompressed: Boolean = false
) {
    var appState = AppState.SCANNING
    var totalChunks: Int? = null
    var receivedCount = 0
    var lastError: String? = null
    var outputPath: String? = null
    var outputSize = 0L
    var missingChunks = listOf<Int>()
    val chunks = ConcurrentHashMap<Int, ByteArray>()

    val isComplete: Boolean
        get() = totalChunks != null && receivedCount == totalChunks

    val displayName: String
        get() = fileName ?: "未命名文件"
}

class MultiFileReceiveManager {
    private val files = mutableMapOf<String, FileReceiveState>()

    fun getOrCreate(fileKey: String, chunk: ChunkInfo): FileReceiveState {
        // Always try to match existing active file first
        // (handles generateFileKey mismatch between seq=0 and seq>0)
        val existing = files.values.firstOrNull {
            it.appState == AppState.SCANNING ||
            it.appState == AppState.RECEIVING ||
            it.appState == AppState.ASSEMBLING
        }
        if (existing != null) {
            // Transfer metadata from seq=0 chunk if existing file lacks it
            if (existing.fileName == null && chunk.fileName != null) {
                existing.fileName = chunk.fileName
                existing.fileCrc32 = chunk.fileCrc32
                existing.fileSize = chunk.fileSize
                existing.isCompressed = chunk.isCompressed
            }
            return existing
        }
        return files.getOrPut(fileKey) {
            FileReceiveState(
                fileKey = fileKey,
                fileName = chunk.fileName,
                fileCrc32 = chunk.fileCrc32,
                fileSize = chunk.fileSize,
                isCompressed = chunk.isCompressed
            )
        }
    }

    fun get(fileKey: String): FileReceiveState? = files[fileKey]

    fun getAll(): List<FileReceiveState> = files.values.toList()

    fun getActiveFiles(): List<FileReceiveState> = files.values.filter {
        it.appState == AppState.SCANNING || it.appState == AppState.RECEIVING
    }

    fun getCompletedFiles(): List<FileReceiveState> = files.values.filter {
        it.appState == AppState.DONE
    }

    fun getFailedFiles(): List<FileReceiveState> = files.values.filter {
        it.appState == AppState.ERROR
    }

    fun clear() {
        files.clear()
    }

    fun generateFileKey(chunk: ChunkInfo): String {
        return "${chunk.fileName ?: "unknown"}_${chunk.fileCrc32 ?: 0}"
    }
}
