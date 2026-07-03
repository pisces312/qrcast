package com.pisces312.qrcast

import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.util.Size
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.Executors
import java.util.zip.CRC32
import org.apache.commons.compress.archivers.sevenz.SevenZFile

class ScanActivity : AppCompatActivity() {

    private lateinit var scanTitle: TextView
    private lateinit var btnCancelReceive: ImageButton
    private lateinit var previewView: PreviewView
    private lateinit var scanFrame: View
    private lateinit var scanHint: TextView
    private lateinit var scanFps: TextView
    private lateinit var fileInfoText: TextView
    private lateinit var fileMetaText: TextView
    private lateinit var receivedChunksText: TextView
    private lateinit var missingChunksText: TextView
    private lateinit var timeEstimateText: TextView
    private lateinit var speedText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var progressPercent: TextView
    private lateinit var progressText: TextView
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
    private val barcodeScanner: BarcodeScanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .build()
    )
    private val cameraExecutor = Executors.newSingleThreadExecutor()

    private val receiveManager = MultiFileReceiveManager()
    private var currentFileKey: String? = null
    private var isProcessing = false
    private val fpsTimestamps = ArrayDeque<Long>(8)
    private var scanFpsValue = 0f
    private var analysisResolution = ""
    private var receiveStartTime = 0L
    private var pendingTempFile: File? = null
    private var pendingFileName: String? = null
    private var pendingFileKey: String? = null
    private var currentMode = ScanMode.CHUNKED
    private var currentQrType = QrType.MONO

    private val saveAsLauncher = registerForActivityResult(
        ActivityResultContracts.CreateDocument("application/octet-stream")
    ) { uri ->
        if (uri != null) {
            saveToChosenUri(uri)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_scan)

        // Read parameters from Intent
        currentQrType = QrType.entries[intent.getIntExtra(EXTRA_QR_TYPE, 0)]
        currentMode = ScanMode.entries[intent.getIntExtra(EXTRA_SCAN_MODE, 0)]

        initViews()
        setupBackPress()

        // Keep screen on setting
        val prefs = getSharedPreferences(SettingsActivity.PREFS_NAME, MODE_PRIVATE)
        if (prefs.getBoolean(SettingsActivity.KEY_KEEP_SCREEN_ON, false)) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }

        // Start camera immediately
        startCamera()
    }

    private fun initViews() {
        scanTitle = findViewById(R.id.scanTitle)
        btnCancelReceive = findViewById(R.id.btnCancelReceive)
        previewView = findViewById(R.id.previewView)
        scanFrame = findViewById(R.id.scanFrame)
        scanHint = findViewById(R.id.scanHint)
        scanFps = findViewById(R.id.scanFps)
        fileInfoText = findViewById(R.id.fileInfoText)
        fileMetaText = findViewById(R.id.fileMetaText)
        receivedChunksText = findViewById(R.id.receivedChunksText)
        missingChunksText = findViewById(R.id.missingChunksText)
        timeEstimateText = findViewById(R.id.timeEstimateText)
        speedText = findViewById(R.id.speedText)
        progressBar = findViewById(R.id.progressBar)
        progressPercent = findViewById(R.id.progressPercent)
        progressText = findViewById(R.id.progressText)
        resultPanel = findViewById(R.id.resultPanel)
        resultFileName = findViewById(R.id.resultFileName)
        resultFileSize = findViewById(R.id.resultFileSize)
        resultContent = findViewById(R.id.resultContent)
        errorPanel = findViewById(R.id.errorPanel)
        errorText = findViewById(R.id.errorText)
        btnContinue = findViewById(R.id.btnContinue)
        loadingIndicator = findViewById(R.id.loadingIndicator)

        // Set title based on QR type
        scanTitle.text = when (currentQrType) {
            QrType.MONO -> "黑白二维码相机扫描"
            QrType.RGB -> "彩色二维码相机扫描"
        }

        findViewById<ImageButton>(R.id.btnBack).setOnClickListener { onBackPressedDispatcher.onBackPressed() }
        btnCancelReceive.setOnClickListener { cancelReceiving() }
        findViewById<Button>(R.id.btnOpen).setOnClickListener { openFile() }
        findViewById<Button>(R.id.btnShare).setOnClickListener { shareFile() }
        findViewById<Button>(R.id.btnReset).setOnClickListener { reset() }
        findViewById<Button>(R.id.btnRetry).setOnClickListener { reset() }
        btnContinue.setOnClickListener { continueReceiving() }

        scanHint.text = getScanHint()
        scanFps.text = "扫描 --fps"
    }

    private fun setupBackPress() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // Always go back to MainActivity
                isEnabled = false
                onBackPressedDispatcher.onBackPressed()
                isEnabled = true
            }
        })
    }

    private fun startCamera() {
        fpsTimestamps.clear()
        scanFpsValue = 0f
        analysisResolution = ""

        // Set initial aspect ratio from requested resolution
        val initialRatio = "${CAMERA_TARGET_WIDTH}:${CAMERA_TARGET_HEIGHT}"
        val previewParams = previewView.layoutParams as androidx.constraintlayout.widget.ConstraintLayout.LayoutParams
        previewParams.dimensionRatio = initialRatio
        previewView.layoutParams = previewParams

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

        val resolutionSelector = ResolutionSelector.Builder()
            .setResolutionStrategy(ResolutionStrategy(
                Size(CAMERA_TARGET_WIDTH, CAMERA_TARGET_HEIGHT),
                ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER
            ))
            .build()

        imageAnalysis = ImageAnalysis.Builder()
            .setResolutionSelector(resolutionSelector)
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

    private fun processImage(imageProxy: ImageProxy) {
        if (isProcessing) {
            imageProxy.close()
            return
        }
        isProcessing = true
        val submitTime = System.currentTimeMillis()

        val mediaImage = imageProxy.image ?: run {
            isProcessing = false
            imageProxy.close()
            return
        }

        // Capture actual camera resolution from first frame
        if (analysisResolution.isEmpty()) {
            val w = mediaImage.width
            val h = mediaImage.height
            analysisResolution = "${w}×${h}"
            val ratio = "$w:$h"
            runOnUiThread {
                val previewParams = previewView.layoutParams as androidx.constraintlayout.widget.ConstraintLayout.LayoutParams
                previewParams.dimensionRatio = ratio
                previewView.layoutParams = previewParams
                // scanFrame follows previewView bounds automatically
            }
        }

        val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)

        barcodeScanner.process(image)
            .addOnSuccessListener { barcodes ->
                val now = System.currentTimeMillis()
                fpsTimestamps.addLast(now)
                while (fpsTimestamps.size > 8) fpsTimestamps.removeFirst()
                if (fpsTimestamps.size >= 2) {
                    val span = fpsTimestamps.last() - fpsTimestamps.first()
                    if (span > 0) {
                        scanFpsValue = ((fpsTimestamps.size - 1) * 1000f / span).coerceIn(0.1f, 60f)
                    }
                }
                val elapsed = now - submitTime
                scanFps.text = "%s  扫描%.0ffps  解码%dms".format(analysisResolution, scanFpsValue, elapsed)

                if (barcodes.isNotEmpty()) {
                    onDetect(barcodes)
                }
            }
            .addOnCompleteListener {
                isProcessing = false
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

        LogCollector.i(TAG, "原始数据已保存: ${outFile.absolutePath}")
        showRawResult(contents, outFile)
    }

    private fun handleChunkedMode(barcodes: List<Barcode>) {
        val potentialChunks = mutableListOf<ChunkInfo>()
        for (barcode in barcodes) {
            val raw = barcode.rawBytes ?: continue
            val chunk = parsePayloadV2(raw) ?: continue
            potentialChunks.add(chunk)
        }
        processChunkList(potentialChunks)
    }

    private fun processChunkList(potentialChunks: List<ChunkInfo>) {
        if (potentialChunks.isEmpty()) return

        val chunksByFile = potentialChunks.groupBy { receiveManager.generateFileKey(it) }
        for ((fileKey, chunks) in chunksByFile) {
            processFileChunks(fileKey, chunks)
        }
    }

    private fun processFileChunks(fileKey: String, chunks: List<ChunkInfo>) {
        if (chunks.isEmpty()) return

        val firstChunk = chunks.first()
        val fileState = receiveManager.getOrCreate(fileKey, firstChunk)

        if (fileState.appState != AppState.SCANNING &&
            fileState.appState != AppState.RECEIVING) {
            return
        }

        if (currentFileKey == null && fileState.appState == AppState.RECEIVING) {
            currentFileKey = fileKey
        }

        val totalCounts = mutableMapOf<Int, Int>()
        for (chunk in chunks) {
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

        val validChunks = chunks.filter {
            consensusTotal != null && it.total == consensusTotal && it.seq < it.total
        }

        var hasNewChunk = false
        for (chunk in validChunks) {
            if (fileState.chunks.containsKey(chunk.seq)) continue

            if (fileState.totalChunks == null) {
                fileState.totalChunks = chunk.total
                fileState.appState = AppState.RECEIVING
                if (currentFileKey == null) {
                    currentFileKey = fileKey
                    runOnUiThread { showReceiving() }
                }
            }

            fileState.chunks[chunk.seq] = chunk.payload
            fileState.totalPayloadBytes += chunk.payload.size
            fileState.receivedCount = fileState.chunks.size
            hasNewChunk = true
        }

        if (hasNewChunk) {
            runOnUiThread { updateProgress() }

            if (fileState.isComplete) {
                lifecycleScope.launch { assembleFile(fileState) }
            }
        }
    }

    private fun showReceiving() {
        receiveStartTime = System.currentTimeMillis()
        scanHint.visibility = View.GONE
        btnCancelReceive.visibility = View.VISIBLE

        fileInfoText.text = "正在接收..."
        receivedChunksText.text = "已收到: --"
        missingChunksText.text = "缺失: --"
        progressText.text = "0/--"
        timeEstimateText.text = "-- / --"
        speedText.text = ""

        val outDir = SettingsActivity.getOutputDir(this)
        fileMetaText.text = "保存位置: ${outDir.absolutePath}"

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
        val activeFiles = receiveManager.getActiveFiles()
        val completedFiles = receiveManager.getCompletedFiles()

        if (activeFiles.isEmpty() && completedFiles.isEmpty()) return

        val totalReceived = activeFiles.sumOf { it.receivedCount } + completedFiles.sumOf { it.totalChunks ?: 0 }
        val totalExpected = activeFiles.sumOf { it.totalChunks ?: 0 } + completedFiles.sumOf { it.totalChunks ?: 0 }
        val pct = if (totalExpected > 0) (totalReceived * 100 / totalExpected) else 0

        progressText.text = "$totalReceived/$totalExpected"
        progressBar.progress = pct
        progressPercent.text = "$pct%"

        val currentFile = activeFiles.firstOrNull() ?: completedFiles.lastOrNull()
        if (currentFile != null) {
            fileInfoText.text = currentFile.displayName
            val meta = StringBuilder("原始大小: ${formatBytes(currentFile.fileSize ?: 0)}")
            if (currentFile.isCompressed) meta.append(" · 7z压缩")
            fileMetaText.text = meta.toString()

            val total = currentFile.totalChunks ?: 0
            val receivedIds = currentFile.chunks.keys.sorted()
            val missingIds = (0 until total).filter { !currentFile.chunks.containsKey(it) }

            receivedChunksText.text = "已收到 (${receivedIds.size}): ${receivedIds.truncate(15)}"
            if (missingIds.isEmpty()) {
                missingChunksText.text = "无缺失"
            } else {
                missingChunksText.text = "缺失 (${missingIds.size}): ${missingIds.truncate(15)}"
            }

            val elapsed = (System.currentTimeMillis() - receiveStartTime) / 1000.0
            val chunkSpeed = if (elapsed > 0.5) totalReceived / elapsed else 0.0
            if (chunkSpeed > 0 && totalExpected > totalReceived) {
                val eta = totalExpected / chunkSpeed
                timeEstimateText.text = "%.1fs / %.1fs".format(elapsed, eta)
            } else {
                timeEstimateText.text = "%.1fs / --".format(elapsed)
            }

            // Use actual received byte count
            val totalPayloadBytes = activeFiles.sumOf { it.totalPayloadBytes } + completedFiles.sumOf { it.totalPayloadBytes }
            val bytesPerSec = if (elapsed > 0.5) (totalPayloadBytes / elapsed).toLong() else 0L
            speedText.text = if (bytesPerSec > 0) "${formatBytes(bytesPerSec)}/s" else ""
        }
    }

    private fun List<Int>.truncate(max: Int): String {
        return if (size <= max) joinToString(", ")
        else "${take(max).joinToString(", ")}... 等${size}块"
    }

    private suspend fun assembleFile(fileState: FileReceiveState) {
        if (fileState.appState == AppState.ASSEMBLING) return
        fileState.appState = AppState.ASSEMBLING

        // 立即停止相机，防止组装期间扫到新文件分块覆盖当前进度信息
        // (背景进度条/文件名应保持上一轮的完成状态，直到用户处理完对话框开始新接收)
        withContext(Dispatchers.Main) { stopCamera() }

        withContext(Dispatchers.IO) {
            try {
                val sortedKeys = fileState.chunks.keys.sorted()
                val estimatedSize = sortedKeys.size * 256
                val bos = ByteArrayOutputStream(estimatedSize)
                for (key in sortedKeys) {
                    bos.write(fileState.chunks[key]!!)
                }
                var data = bos.toByteArray()

                if (fileState.totalChunks != null &&
                    fileState.receivedCount < fileState.totalChunks!!) {
                    val missing = (0 until fileState.totalChunks!!).filter {
                        !fileState.chunks.containsKey(it)
                    }
                    fileState.missingChunks = missing
                    fileState.lastError = "不完整: ${fileState.receivedCount}/${fileState.totalChunks}，" +
                            "缺失分块: ${missing.take(10).joinToString(", ")}" +
                            if (missing.size > 10) "..." else ""
                    fileState.appState = AppState.ERROR
                    withContext(Dispatchers.Main) { updateProgress() }
                    return@withContext
                }

                if (fileState.isCompressed) {
                    LogCollector.i(TAG, "[${fileState.fileKey}] Decompressing 7z data (${data.size} bytes)")
                    val decompressed = decompress7z(data)
                    if (decompressed == null) {
                        fileState.appState = AppState.ERROR
                        fileState.lastError = "7z 解压失败"
                        withContext(Dispatchers.Main) { updateProgress() }
                        return@withContext
                    }
                    LogCollector.i(TAG, "[${fileState.fileKey}] Decompressed: ${decompressed.size} bytes")
                    data = decompressed
                }

                if (fileState.fileSize != null && data.size.toLong() != fileState.fileSize) {
                    LogCollector.w(TAG, "[${fileState.fileKey}] File size mismatch")
                    fileState.appState = AppState.ERROR
                    fileState.lastError = "文件大小不匹配: 期望 ${fileState.fileSize}, 实际 ${data.size}"
                    withContext(Dispatchers.Main) { updateProgress() }
                    return@withContext
                }

                val expectedCrc = fileState.fileCrc32
                if (expectedCrc != null) {
                    val crc = CRC32()
                    crc.update(data)
                    val actualCrc = crc.value
                    if (actualCrc != expectedCrc) {
                        LogCollector.w(TAG, "[${fileState.fileKey}] CRC32 mismatch")
                        fileState.appState = AppState.ERROR
                        fileState.lastError = "CRC32 校验失败"
                        withContext(Dispatchers.Main) { updateProgress() }
                        return@withContext
                    }
                    LogCollector.i(TAG, "[${fileState.fileKey}] CRC32 verified")
                }

                fileState.outputSize = data.size.toLong()

                val outName = if (!fileState.fileName.isNullOrEmpty()) {
                    fileState.fileName!!
                } else {
                    detectExtension(data)
                }

                val tempFile = File.createTempFile("qrcast_pending_", ".tmp", cacheDir)
                tempFile.deleteOnExit()
                tempFile.writeBytes(data)

                pendingTempFile = tempFile
                pendingFileName = outName
                pendingFileKey = fileState.fileKey

                fileState.appState = AppState.DONE
                LogCollector.i(TAG, "[${fileState.fileKey}] File assembled: $outName (${formatBytes(data.size.toLong())})")

                withContext(Dispatchers.Main) {
                    updateProgress()
                    showSaveDialog(outName, data.size.toLong())
                }
            } catch (e: Exception) {
                LogCollector.e(TAG, "[${fileState.fileKey}] 文件组装失败", e)
                fileState.appState = AppState.ERROR
                fileState.lastError = e.message
                withContext(Dispatchers.Main) { updateProgress() }
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

    private fun decompress7z(data: ByteArray): ByteArray? {
        return try {
            val tempFile = File.createTempFile("qrcast_", ".7z", cacheDir)
            tempFile.deleteOnExit()
            tempFile.writeBytes(data)

            val extractor = SevenZFile.builder().setFile(tempFile).get()
            val entry = extractor.nextEntry ?: run {
                extractor.close()
                tempFile.delete()
                return null
            }

            val buffer = ByteArrayOutputStream()
            val buf = ByteArray(65536)
            var len: Int
            while (extractor.read(buf).also { len = it } != -1) {
                buffer.write(buf, 0, len)
            }
            extractor.close()
            tempFile.delete()
            buffer.toByteArray()
        } catch (e: Exception) {
            LogCollector.e(TAG, "7z decompression failed", e)
            null
        }
    }

    private fun showRawResult(contents: List<String>, outFile: File) {
        resultPanel.visibility = View.VISIBLE
        findViewById<TextView>(R.id.resultTitle).text = "识别结果"
        resultFileName.visibility = View.GONE
        resultFileSize.visibility = View.GONE
        resultContent.visibility = View.VISIBLE
        resultContent.text = "文件已保存到: ${outFile.absolutePath}\n\n" + contents.joinToString("\n\n---\n\n")
    }

    private fun showDone() {
        loadingIndicator.visibility = View.GONE
        resultPanel.visibility = View.VISIBLE

        val completedFiles = receiveManager.getCompletedFiles()
        if (completedFiles.size == 1) {
            val file = completedFiles.first()
            findViewById<TextView>(R.id.resultTitle).text = "接收完成！"
            resultFileName.visibility = View.VISIBLE
            resultFileSize.visibility = View.VISIBLE
            resultContent.visibility = View.GONE
            resultFileName.text = file.displayName
            resultFileSize.text = formatBytes(file.outputSize)
        } else {
            findViewById<TextView>(R.id.resultTitle).text = "接收完成 ${completedFiles.size} 个文件！"
            resultFileName.visibility = View.VISIBLE
            resultFileSize.visibility = View.VISIBLE
            resultContent.visibility = View.VISIBLE
            val sb = StringBuilder()
            for (file in completedFiles) {
                sb.appendLine("${file.displayName} (${formatBytes(file.outputSize)})")
            }
            resultFileName.text = ""
            resultFileSize.text = ""
            resultContent.text = sb.toString()
        }
    }

    private fun showError(message: String, showContinue: Boolean = false) {
        loadingIndicator.visibility = View.GONE
        errorPanel.visibility = View.VISIBLE
        errorText.text = message
        btnContinue.visibility = if (showContinue) View.VISIBLE else View.GONE
    }

    private fun showSaveDialog(fileName: String, fileSize: Long) {
        if (pendingTempFile == null) return
        val message = "文件: $fileName\n大小: ${formatBytes(fileSize)}"

        AlertDialog.Builder(this)
            .setTitle("接收成功!")
            .setMessage(message)
            .setPositiveButton("保存到默认路径") { _, _ ->
                saveToDefaultPath()
            }
            .setNeutralButton("另存为...") { _, _ ->
                saveAsLauncher.launch(fileName)
            }
            .setNegativeButton("取消") { _, _ ->
                pendingTempFile?.delete()
                pendingTempFile = null
                pendingFileName = null
                pendingFileKey = null
            }
            .setCancelable(false)
            .show()
    }

    private fun saveToDefaultPath() {
        val tempFile = pendingTempFile ?: return
        val outName = pendingFileName ?: return
        val fileKey = pendingFileKey ?: return

        val outDir = SettingsActivity.getOutputDir(this)
        if (!outDir.exists()) outDir.mkdirs()

        val outFile = File(outDir, outName)
        tempFile.copyTo(outFile, overwrite = true)
        tempFile.delete()

        val fileState = receiveManager.get(fileKey)
        fileState?.outputPath = outFile.absolutePath

        pendingTempFile = null
        pendingFileName = null
        pendingFileKey = null

        Toast.makeText(this, "已保存到: ${outFile.absolutePath}", Toast.LENGTH_LONG).show()
        showDone()
    }

    private fun saveToChosenUri(uri: Uri) {
        val tempFile = pendingTempFile ?: return
        val fileKey = pendingFileKey ?: return

        try {
            contentResolver.openOutputStream(uri)?.use { output ->
                tempFile.inputStream().use { input ->
                    input.copyTo(output)
                }
            }
            val fileState = receiveManager.get(fileKey)
            fileState?.outputPath = uri.toString()

            tempFile.delete()
            pendingTempFile = null
            pendingFileName = null
            pendingFileKey = null

            Toast.makeText(this, "文件已保存", Toast.LENGTH_SHORT).show()
            showDone()
        } catch (e: Exception) {
            LogCollector.e(TAG, "Failed to save file", e)
            Toast.makeText(this, "保存失败: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun openFile() {
        val completedFiles = receiveManager.getCompletedFiles()
        if (completedFiles.isEmpty()) return

        val path = completedFiles[0].outputPath ?: return
        val file = File(path)
        val uri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, getMimeType(file))
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(intent, "打开文件"))
    }

    private fun shareFile() {
        val completedFiles = receiveManager.getCompletedFiles()
        if (completedFiles.isEmpty()) return

        val path = completedFiles[0].outputPath ?: return
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

    private fun cancelReceiving() {
        receiveManager.clear()
        currentFileKey = null
        // Go back to MainActivity
        finish()
    }

    private fun reset() {
        receiveManager.clear()
        currentFileKey = null
        resultPanel.visibility = View.GONE
        errorPanel.visibility = View.GONE
        loadingIndicator.visibility = View.GONE
        btnCancelReceive.visibility = View.GONE

        // Restart camera and scanning
        startCamera()
    }

    private fun continueReceiving() {
        val activeFiles = receiveManager.getActiveFiles()
        for (file in activeFiles) {
            file.appState = AppState.RECEIVING
            file.lastError = null
        }
        errorPanel.visibility = View.GONE
        resultPanel.visibility = View.GONE
        showReceiving()
        startCamera()
    }

    private fun stopCamera() {
        imageAnalysis?.clearAnalyzer()
        cameraProvider?.unbindAll()
    }

    private fun formatBytes(bytes: Long): String {
        return when {
            bytes < 1024 -> "$bytes B"
            bytes < 1024 * 1024 -> String.format("%.2f KB", bytes / 1024.0)
            else -> String.format("%.2f MB", bytes / (1024.0 * 1024.0))
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
        barcodeScanner.close()
    }

    companion object {
        private const val TAG = "QRCast.Scan"
        const val EXTRA_QR_TYPE = "qr_type"
        const val EXTRA_SCAN_MODE = "scan_mode"
        const val CAMERA_TARGET_WIDTH = 1280
        const val CAMERA_TARGET_HEIGHT = 960
    }
}
