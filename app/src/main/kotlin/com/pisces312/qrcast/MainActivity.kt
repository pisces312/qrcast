package com.pisces312.qrcast

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.view.View
import android.widget.Button
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors
import java.util.zip.CRC32

class MainActivity : AppCompatActivity() {

    private lateinit var toolbar: LinearLayout
    private lateinit var qrTypeGroup: RadioGroup
    private lateinit var protocolGroup: RadioGroup
    private lateinit var rbMono: View
    private lateinit var rbRgb: View
    private lateinit var rbChunked: View
    private lateinit var rbRaw: View
    private lateinit var sourcePanel: LinearLayout
    private lateinit var previewView: PreviewView
    private lateinit var scanFrame: View
    private lateinit var scanHint: TextView
    private lateinit var progressOverlay: LinearLayout
    private lateinit var progressText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var progressPercent: TextView
    private lateinit var detailPanel: LinearLayout
    private lateinit var fileInfoText: TextView
    private lateinit var fileMetaText: TextView
    private lateinit var receivedChunksText: TextView
    private lateinit var missingChunksText: TextView
    private lateinit var resultPanel: LinearLayout
    private lateinit var resultFileName: TextView
    private lateinit var resultFileSize: TextView
    private lateinit var resultContent: TextView
    private lateinit var errorPanel: LinearLayout
    private lateinit var errorText: TextView
    private lateinit var btnContinue: Button
    private lateinit var loadingIndicator: View

    private var cameraProvider: ProcessCameraProvider? = null
    private var imageAnalysis: ImageAnalysis? = null
    private val barcodeScanner: BarcodeScanner = BarcodeScanning.getClient()
    private val cameraExecutor = Executors.newSingleThreadExecutor()

    private var receiveState = ReceiveState()
    private var lastProcessTime = 0L
    private val throttleMs = 200
    private var currentMode = ScanMode.CHUNKED
    private var currentQrType = QrType.MONO

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            startCameraMode()
        } else {
            showError("需要相机权限才能扫描QR码")
        }
    }

    private val galleryLauncher = registerForActivityResult(
        ActivityResultContracts.GetMultipleContents()
    ) { uris ->
        if (uris.isNotEmpty()) {
            processGalleryImages(uris)
        }
    }

    private val openDocumentLauncher = registerForActivityResult(
        ActivityResultContracts.OpenMultipleDocuments()
    ) { uris ->
        if (uris.isNotEmpty()) {
            processGalleryImages(uris)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initViews()
    }

    private fun initViews() {
        toolbar = findViewById(R.id.toolbar)
        qrTypeGroup = findViewById(R.id.qrTypeGroup)
        protocolGroup = findViewById(R.id.protocolGroup)
        rbMono = findViewById(R.id.rbMono)
        rbRgb = findViewById(R.id.rbRgb)
        rbChunked = findViewById(R.id.rbChunked)
        rbRaw = findViewById(R.id.rbRaw)
        sourcePanel = findViewById(R.id.sourcePanel)
        previewView = findViewById(R.id.previewView)
        scanFrame = findViewById(R.id.scanFrame)
        scanHint = findViewById(R.id.scanHint)
        progressOverlay = findViewById(R.id.progressOverlay)
        progressText = findViewById(R.id.progressText)
        progressBar = findViewById(R.id.progressBar)
        progressPercent = findViewById(R.id.progressPercent)
        detailPanel = findViewById(R.id.detailPanel)
        fileInfoText = findViewById(R.id.fileInfoText)
        fileMetaText = findViewById(R.id.fileMetaText)
        receivedChunksText = findViewById(R.id.receivedChunksText)
        missingChunksText = findViewById(R.id.missingChunksText)
        resultPanel = findViewById(R.id.resultPanel)
        resultFileName = findViewById(R.id.resultFileName)
        resultFileSize = findViewById(R.id.resultFileSize)
        resultContent = findViewById(R.id.resultContent)
        errorPanel = findViewById(R.id.errorPanel)
        errorText = findViewById(R.id.errorText)
        btnContinue = findViewById(R.id.btnContinue)
        loadingIndicator = findViewById(R.id.loadingIndicator)

        findViewById<LinearLayout>(R.id.btnCamera).setOnClickListener { onCameraSelected() }
        findViewById<LinearLayout>(R.id.btnGallery).setOnClickListener { onGallerySelected() }
        findViewById<ImageButton>(R.id.btnSettings).setOnClickListener { openSettings() }
        findViewById<ImageButton>(R.id.btnLogs).setOnClickListener { openLogs() }
        findViewById<Button>(R.id.btnOpen).setOnClickListener { openFile() }
        findViewById<Button>(R.id.btnShare).setOnClickListener { shareFile() }
        findViewById<Button>(R.id.btnReset).setOnClickListener { reset() }
        findViewById<Button>(R.id.btnRetry).setOnClickListener { reset() }
        btnContinue.setOnClickListener { continueReceiving() }

        qrTypeGroup.setOnCheckedChangeListener { _, checkedId ->
            currentQrType = when (checkedId) {
                R.id.rbRgb -> QrType.RGB
                else -> QrType.MONO
            }
            LogCollector.i(TAG, "切换二维码类型: $currentQrType")
        }

        protocolGroup.setOnCheckedChangeListener { _, checkedId ->
            currentMode = when (checkedId) {
                R.id.rbRaw -> ScanMode.RAW
                else -> ScanMode.CHUNKED
            }
            LogCollector.i(TAG, "切换模式: $currentMode")
        }
    }

    private fun onCameraSelected() {
        LogCollector.i(TAG, "用户选择相机扫码，模式: $currentMode")
        when {
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
                    PackageManager.PERMISSION_GRANTED -> {
                startCameraMode()
            }
            shouldShowRequestPermissionRationale(Manifest.permission.CAMERA) -> {
                requestPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
            else -> {
                requestPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }

    private fun onGallerySelected() {
        LogCollector.i(TAG, "用户选择图库选图，模式: $currentMode")
        openDocumentLauncher.launch(arrayOf("image/*"))
    }

    private fun openSettings() {
        startActivity(Intent(this, SettingsActivity::class.java))
    }

    private fun openLogs() {
        startActivity(Intent(this, LogActivity::class.java))
    }

    private fun startCameraMode() {
        sourcePanel.visibility = View.GONE
        previewView.visibility = View.VISIBLE
        scanFrame.visibility = View.VISIBLE
        scanHint.visibility = View.VISIBLE
        scanHint.text = getScanHint()

        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            try {
                cameraProvider = cameraProviderFuture.get()
                bindCameraUseCases()
            } catch (e: Exception) {
                LogCollector.e(TAG, "相机初始化失败", e)
                showError("相机初始化失败: ${e.message}")
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun bindCameraUseCases() {
        val provider = cameraProvider ?: return

        val preview = Preview.Builder()
            .build()
            .also { it.surfaceProvider = previewView.surfaceProvider }

        imageAnalysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
            .also {
                it.setAnalyzer(cameraExecutor) { imageProxy ->
                    processImage(imageProxy)
                }
            }

        val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

        try {
            provider.unbindAll()
            provider.bindToLifecycle(this, cameraSelector, preview, imageAnalysis)
        } catch (e: Exception) {
            LogCollector.e(TAG, "Use case binding failed", e)
        }
    }

    private fun processGalleryImages(uris: List<Uri>) {
        if (uris.isEmpty()) return

        loadingIndicator.visibility = View.VISIBLE
        sourcePanel.visibility = View.GONE

        lifecycleScope.launch(Dispatchers.IO) {
            val allBarcodes = mutableListOf<Barcode>()
            for (uri in uris) {
                try {
                    val image = InputImage.fromFilePath(this@MainActivity, uri)
                    val barcodes = barcodeScanner.process(image).await()
                    allBarcodes.addAll(barcodes)
                } catch (e: Exception) {
                    LogCollector.e(TAG, "图库图片解析失败: $uri", e)
                }
            }

            withContext(Dispatchers.Main) {
                loadingIndicator.visibility = View.GONE
                if (allBarcodes.isNotEmpty()) {
                    onDetect(allBarcodes)
                } else {
                    showError("未在图片中检测到二维码")
                }
            }
        }
    }

    private fun processImage(imageProxy: ImageProxy) {
        val now = System.currentTimeMillis()
        if (now - lastProcessTime < throttleMs) {
            imageProxy.close()
            return
        }
        lastProcessTime = now

        val mediaImage = imageProxy.image ?: run {
            imageProxy.close()
            return
        }

        val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)

        barcodeScanner.process(image)
            .addOnSuccessListener { barcodes ->
                if (barcodes.isNotEmpty()) {
                    onDetect(barcodes)
                }
            }
            .addOnCompleteListener {
                imageProxy.close()
            }
    }

    private fun onDetect(barcodes: List<Barcode>) {
        when (currentMode) {
            ScanMode.RAW -> handleRawMode(barcodes)
            ScanMode.CHUNKED -> handleChunkedMode(barcodes)
        }
    }

    private fun handleRawMode(barcodes: List<Barcode>) {
        val contents = barcodes.mapNotNull { barcode ->
            barcode.rawBytes?.let { bytes ->
                try {
                    String(bytes, Charsets.UTF_8)
                } catch (e: Exception) {
                    bytes.joinToString(" ") { "0x%02X".format(it) }
                }
            } ?: barcode.displayValue
        }

        if (contents.isEmpty()) return

        stopCamera()

        val outDir = SettingsActivity.getOutputDir(this)
        if (!outDir.exists()) outDir.mkdirs()
        val outFile = File(outDir, SettingsActivity.generateTimestampFileName("txt"))
        outFile.writeText(contents.joinToString("\n\n---\n\n"))
        receiveState.outputPath = outFile.absolutePath
        receiveState.fileName = outFile.name
        receiveState.outputSize = outFile.length().toInt()

        LogCollector.i(TAG, "原始数据已保存: ${outFile.absolutePath}")
        showRawResult(contents)
    }

    private fun showRawResult(contents: List<String>) {
        resultPanel.visibility = View.VISIBLE
        findViewById<TextView>(R.id.resultTitle).text = "识别结果"
        resultFileName.visibility = View.GONE
        resultFileSize.visibility = View.GONE
        resultContent.visibility = View.VISIBLE
        resultContent.text = contents.joinToString("\n\n---\n\n")
    }

    private fun handleChunkedMode(barcodes: List<Barcode>) {
        if (receiveState.appState != AppState.SCANNING &&
            receiveState.appState != AppState.RECEIVING) {
            return
        }

        val potentialChunks = mutableListOf<ChunkInfo>()
        for (barcode in barcodes) {
            val raw = barcode.rawBytes ?: continue
            val chunk = parsePayloadV2(raw) ?: continue
            potentialChunks.add(chunk)
        }

        if (potentialChunks.isEmpty()) return

        val totalCounts = mutableMapOf<Int, Int>()
        for (chunk in potentialChunks) {
            totalCounts[chunk.total] = (totalCounts[chunk.total] ?: 0) + 1
        }

        var consensusTotal: Int? = null
        var maxCount = 0
        for ((total, count) in totalCounts) {
            if (count > maxCount) {
                maxCount = count
                consensusTotal = total
            }
        }

        val validChunks = potentialChunks.filter {
            consensusTotal != null && it.total == consensusTotal && it.seq < it.total
        }

        var hasNewChunk = false
        for (chunk in validChunks) {
            if (receiveState.chunks.containsKey(chunk.seq)) continue

            if (receiveState.totalChunks == null) {
                receiveState.totalChunks = chunk.total
                receiveState.appState = AppState.RECEIVING
                runOnUiThread { showReceiving() }
            }

            // seq==0 carries metadata
            if (chunk.seq == 0) {
                receiveState.fileName = chunk.fileName
                receiveState.fileCrc32 = chunk.fileCrc32
                receiveState.fileSize = chunk.fileSize
                receiveState.isCompressed = chunk.isCompressed
                LogCollector.i(TAG, "收到元数据: name=${chunk.fileName}, size=${chunk.fileSize}, compressed=${chunk.isCompressed}")
            }

            receiveState.chunks[chunk.seq] = chunk.payload
            receiveState.receivedCount = receiveState.chunks.size
            hasNewChunk = true

            LogCollector.d(TAG, "收到分块 ${chunk.seq + 1}/${chunk.total}")
        }

        if (hasNewChunk) {
            runOnUiThread { updateProgress() }

            if (receiveState.isComplete) {
                lifecycleScope.launch { assemble() }
            }
        }
    }

    private fun parsePayloadV2(raw: ByteArray): ChunkInfo? {
        if (raw.size < 12) return null
        val buffer = ByteBuffer.wrap(raw).order(ByteOrder.BIG_ENDIAN)
        val seq = buffer.int
        val total = buffer.int
        val dataLen = buffer.short.toInt() and 0xFFFF
        val protoVer = buffer.get().toInt() and 0xFF
        val flags = buffer.get().toInt() and 0xFF

        if (protoVer != 0x02) return null
        if (dataLen > raw.size - 12) return null

        val dataSegment = raw.copyOfRange(12, 12 + dataLen)

        var fileName: String? = null
        var fileCrc32: Long? = null
        var fileSize: Int? = null
        var payload = dataSegment

        if (seq == 0) {
            if (dataSegment.isEmpty()) return null
            val fileNameLen = dataSegment[0].toInt() and 0xFF
            if (1 + fileNameLen + 8 > dataSegment.size) return null
            fileName = String(dataSegment, 1, fileNameLen, Charsets.UTF_8)
            val metaBuf = ByteBuffer.wrap(dataSegment, 1 + fileNameLen, 8).order(ByteOrder.BIG_ENDIAN)
            fileCrc32 = metaBuf.int.toLong() and 0xFFFFFFFFL
            fileSize = metaBuf.int
            payload = dataSegment.copyOfRange(1 + fileNameLen + 8, dataSegment.size)
        }

        return ChunkInfo(
            seq = seq,
            total = total,
            payload = payload,
            fileName = fileName,
            fileCrc32 = fileCrc32,
            fileSize = fileSize,
            isCompressed = (flags and 0x01) != 0
        )
    }

    private fun showReceiving() {
        progressOverlay.visibility = View.VISIBLE
        detailPanel.visibility = View.VISIBLE
        scanHint.text = getScanHint()
        updateProgress()
    }

    private fun getScanHint(): String {
        val typeName = when (currentQrType) {
            QrType.MONO -> "黑白"
            QrType.RGB -> "彩色"
        }
        val modeName = when (currentMode) {
            ScanMode.CHUNKED -> "接收中"
            ScanMode.RAW -> "原始数据"
        }
        return "对准${typeName}二维码 ($modeName)"
    }

    private fun updateProgress() {
        val total = receiveState.totalChunks ?: 0
        val received = receiveState.receivedCount
        val pct = if (total > 0) (received * 100 / total) else 0

        progressText.text = "$received/$total"
        progressBar.progress = pct
        progressPercent.text = "$pct%"

        // 文件信息
        val name = receiveState.fileName
        val size = receiveState.fileSize
        if (name != null && size != null) {
            fileInfoText.text = name
            val meta = StringBuilder("原始大小: ${formatBytes(size)}")
            if (receiveState.isCompressed) meta.append(" · 7z压缩")
            fileMetaText.text = meta.toString()
        } else {
            fileInfoText.text = "等待元数据..."
            fileMetaText.text = "扫描第0块获取文件信息"
        }

        // chunk 状态
        val receivedIds = receiveState.chunks.keys.sorted()
        val missingIds = (0 until total).filter { it !in receiveState.chunks }

        receivedChunksText.text = "已收到 (${receivedIds.size}): ${receivedIds.truncate(15)}"
        if (missingIds.isEmpty()) {
            missingChunksText.visibility = View.GONE
        } else {
            missingChunksText.visibility = View.VISIBLE
            missingChunksText.text = "缺失 (${missingIds.size}): ${missingIds.truncate(15)}"
        }
    }

    private fun List<Int>.truncate(max: Int): String {
        return if (size <= max) joinToString(", ")
        else "${take(max).joinToString(", ")}... 等${size}块"
    }

    private suspend fun assemble() {
        if (receiveState.appState == AppState.ASSEMBLING) return
        receiveState.appState = AppState.ASSEMBLING

        withContext(Dispatchers.Main) {
            progressOverlay.visibility = View.GONE
            loadingIndicator.visibility = View.VISIBLE
            stopCamera()
        }

        withContext(Dispatchers.IO) {
            try {
                val sortedKeys = receiveState.chunks.keys.sorted()
                val fullData = mutableListOf<Byte>()
                for (key in sortedKeys) {
                    fullData.addAll(receiveState.chunks[key]!!.toList())
                }
                val data = fullData.toByteArray()

                if (receiveState.totalChunks != null &&
                    receiveState.receivedCount < receiveState.totalChunks!!) {
                    val missing = (0 until receiveState.totalChunks!!).filter {
                        !receiveState.chunks.containsKey(it)
                    }

                    receiveState.missingChunks = missing
                    receiveState.lastError = "不完整: ${receiveState.receivedCount}/${receiveState.totalChunks}，" +
                            "缺失分块: ${missing.take(10).joinToString(", ")}" +
                            if (missing.size > 10) "..." else ""

                    withContext(Dispatchers.Main) {
                        showError(receiveState.lastError!!, missing.isNotEmpty())
                    }
                    return@withContext
                }

                receiveState.outputSize = data.size

                val outDir = SettingsActivity.getOutputDir(this@MainActivity)
                if (!outDir.exists()) outDir.mkdirs()

                // Use filename from metadata if available, otherwise detect by magic bytes
                val outName = if (!receiveState.fileName.isNullOrEmpty()) {
                    receiveState.fileName!!
                } else {
                    detectExtension(data)
                }

                val outFile = File(outDir, outName)
                outFile.writeBytes(data)

                receiveState.outputPath = outFile.absolutePath
                receiveState.fileName = outName

                // CRC32 verification
                val expectedCrc = receiveState.fileCrc32
                if (expectedCrc != null) {
                    val crc = CRC32()
                    crc.update(data)
                    val actualCrc = crc.value
                    if (actualCrc != expectedCrc) {
                        LogCollector.w(TAG, "CRC32 不匹配: expected=$expectedCrc, actual=$actualCrc")
                        withContext(Dispatchers.Main) {
                            showError("警告: CRC32 校验失败，文件可能损坏", false)
                        }
                        return@withContext
                    }
                    LogCollector.i(TAG, "CRC32 校验通过")
                }

                LogCollector.i(TAG, "文件接收完成: $outName (${formatBytes(data.size)})")

                withContext(Dispatchers.Main) {
                    showDone()
                }
            } catch (e: Exception) {
                LogCollector.e(TAG, "文件组装失败", e)
                withContext(Dispatchers.Main) {
                    showError("文件组装失败: ${e.message}")
                }
            }
        }
    }

    private fun detectExtension(data: ByteArray): String {
        if (data.isEmpty()) return SettingsActivity.generateTimestampFileName("bin")
        return when {
            data[0].toInt() == 0x37 -> SettingsActivity.generateTimestampFileName("7z")
            data[0].toInt() == 0x50 && data.size > 1 && data[1].toInt() == 0x4B ->
                SettingsActivity.generateTimestampFileName("zip")
            else -> SettingsActivity.generateTimestampFileName("bin")
        }
    }

    private fun showDone() {
        loadingIndicator.visibility = View.GONE
        progressOverlay.visibility = View.GONE
        detailPanel.visibility = View.GONE
        resultPanel.visibility = View.VISIBLE
        findViewById<TextView>(R.id.resultTitle).text = "接收完成！"
        resultFileName.visibility = View.VISIBLE
        resultFileSize.visibility = View.VISIBLE
        resultContent.visibility = View.GONE
        resultFileName.text = receiveState.fileName
        resultFileSize.text = formatBytes(receiveState.outputSize)
    }

    private fun showError(message: String, showContinue: Boolean = false) {
        loadingIndicator.visibility = View.GONE
        progressOverlay.visibility = View.GONE
        detailPanel.visibility = View.GONE
        errorPanel.visibility = View.VISIBLE
        errorText.text = message
        btnContinue.visibility = if (showContinue) View.VISIBLE else View.GONE
    }

    private fun openFile() {
        val path = receiveState.outputPath ?: return
        val file = File(path)
        val uri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)

        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, getMimeType(file))
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(intent, "打开文件"))
    }

    private fun shareFile() {
        val path = receiveState.outputPath ?: return
        val file = File(path)
        val uri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)

        val intent = Intent(Intent.ACTION_SEND).apply {
            type = getMimeType(file)
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_TEXT, "通过 QR 码接收的文件")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(intent, "分享文件"))
    }

    private fun getMimeType(file: File): String {
        return when (file.extension.lowercase()) {
            "7z" -> "application/x-7z-compressed"
            "zip" -> "application/zip"
            "txt" -> "text/plain"
            else -> "application/octet-stream"
        }
    }

    private fun reset() {
        receiveState = ReceiveState()
        resultPanel.visibility = View.GONE
        errorPanel.visibility = View.GONE
        progressOverlay.visibility = View.GONE
        detailPanel.visibility = View.GONE
        loadingIndicator.visibility = View.GONE

        previewView.visibility = View.GONE
        scanFrame.visibility = View.GONE
        scanHint.visibility = View.GONE
        sourcePanel.visibility = View.VISIBLE

        stopCamera()
    }

    private fun continueReceiving() {
        receiveState.appState = AppState.RECEIVING
        receiveState.lastError = null
        errorPanel.visibility = View.GONE
        resultPanel.visibility = View.GONE
        showReceiving()
        startCameraMode()
    }

    private fun stopCamera() {
        imageAnalysis?.clearAnalyzer()
        cameraProvider?.unbindAll()
    }

    private fun formatBytes(bytes: Int): String {
        return when {
            bytes < 1024 -> "$bytes B"
            bytes < 1024 * 1024 -> "${bytes / 1024.0} KB"
            bytes < 1024 * 1024 * 1024 -> "${bytes / (1024.0 * 1024.0)} MB"
            else -> "${bytes / (1024.0 * 1024.0 * 1024.0)} GB"
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
        barcodeScanner.close()
    }

    companion object {
        private const val TAG = "QRCast"
    }
}

enum class QrType {
    MONO, RGB
}

enum class ScanMode {
    CHUNKED, RAW
}

enum class AppState {
    SCANNING, RECEIVING, ASSEMBLING, DONE, ERROR
}

class ReceiveState {
    var appState = AppState.SCANNING
    var totalChunks: Int? = null
    var receivedCount = 0
    var lastError: String? = null
    var outputPath: String? = null
    var outputSize = 0
    var fileName: String? = null
    var fileCrc32: Long? = null
    var fileSize: Int? = null
    var isCompressed: Boolean = false
    var missingChunks = listOf<Int>()
    val chunks = mutableMapOf<Int, ByteArray>()

    val isComplete: Boolean
        get() = totalChunks != null && receivedCount == totalChunks
}

data class ChunkInfo(
    val seq: Int,
    val total: Int,
    val payload: ByteArray,
    val fileName: String? = null,
    val fileCrc32: Long? = null,
    val fileSize: Int? = null,
    val isCompressed: Boolean = false
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is ChunkInfo) return false
        return seq == other.seq && total == other.total && payload.contentEquals(other.payload)
    }
    override fun hashCode(): Int = 31 * (31 * seq + total) + payload.contentHashCode()
}

// Extension to convert Task to suspend function
private suspend fun <T> com.google.android.gms.tasks.Task<T>.await(): T {
    return com.google.android.gms.tasks.Tasks.await(this)
}
