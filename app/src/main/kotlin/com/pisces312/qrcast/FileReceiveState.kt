package com.pisces312.qrcast

class FileReceiveState(
    val fileKey: String,
    val fileName: String? = null,
    val fileCrc32: Long? = null,
    val fileSize: Int? = null,
    val isCompressed: Boolean = false
) {
    var appState = AppState.SCANNING
    var totalChunks: Int? = null
    var receivedCount = 0
    var lastError: String? = null
    var outputPath: String? = null
    var outputSize = 0
    var missingChunks = listOf<Int>()
    val chunks = mutableMapOf<Int, ByteArray>()

    val isComplete: Boolean
        get() = totalChunks != null && receivedCount == totalChunks

    val displayName: String
        get() = fileName ?: "未命名文件"
}

class MultiFileReceiveManager {
    private val files = mutableMapOf<String, FileReceiveState>()

    fun getOrCreate(fileKey: String, chunk: ChunkInfo): FileReceiveState {
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
