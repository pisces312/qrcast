package com.pisces312.qrcast

import android.Manifest
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.util.Size
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
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
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors
import java.util.zip.CRC32
import org.apache.commons.compress.archivers.sevenz.SevenZFile

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
    private lateinit var scanFps: TextView
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
    private val barcodeScanner: BarcodeScanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .build()
    )
    private val cameraExecutor = Executors.newSingleThreadExecutor()

    private val receiveManager = MultiFileReceiveManager()
    private var currentFileKey: String? = null
    private var receiveState = ReceiveState() // 保持兼容，实际使用 receiveManager
    private var lastProcessTime = 0L
    private val throttleMs = 80L
    // FPS tracking
    private var lastDetectionTime = 0L
    private var scanFpsValue = 0f
    private var analysisResolution = "" // captured from first frame
    // Pending assembled data awaiting user save decision
    private var pendingData: ByteArray? = null
    private var pendingFileName: String? = null
    private var pendingFileKey: String? = null
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

    private val saveAsLauncher = registerForActivityResult(
        ActivityResultContracts.CreateDocument("application/octet-stream")
    ) { uri ->
        if (uri != null) {
            saveToChosenUri(uri)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Landscape mode setting
        val prefs = getSharedPreferences(SettingsActivity.PREFS_NAME, MODE_PRIVATE)
        if (prefs.getBoolean(SettingsActivity.KEY_LANDSCAPE, false)) {
            requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
        }

        setContentView(R.layout.activity_main)

        initViews()
        setupBackPress()
    }

    private fun setupBackPress() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (progressOverlay.visibility == View.VISIBLE) {
                    cancelReceiving()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                    isEnabled = true
                }
            }
        })
    }

    override fun onResume() {
        super.onResume()
        // Keep screen on setting
        val prefs = getSharedPreferences(SettingsActivity.PREFS_NAME, MODE_PRIVATE)
        if (prefs.getBoolean(SettingsActivity.KEY_KEEP_SCREEN_ON, false)) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
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
        scanFps = findViewById(R.id.scanFps)
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
        findViewById<ImageButton>(R.id.btnHelp).setOnClickListener { openHelp() }
        findViewById<Button>(R.id.btnOpen).setOnClickListener { openFile() }
        findViewById<Button>(R.id.btnShare).setOnClickListener { shareFile() }
        findViewById<Button>(R.id.btnReset).setOnClickListener { reset() }
        findViewById<Button>(R.id.btnRetry).setOnClickListener { reset() }
        findViewById<ImageButton>(R.id.btnCancelReceive).setOnClickListener { cancelReceiving() }
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

    private fun openHelp() {
        startActivity(Intent(this, HelpActivity::class.java))
    }

    private fun startCameraMode() {
        sourcePanel.visibility = View.GONE
        previewView.visibility = View.VISIBLE
        scanFrame.visibility = View.VISIBLE
        scanHint.visibility = View.VISIBLE
        scanFps.visibility = View.VISIBLE
        scanFps.text = "扫描 -- fps"
        lastDetectionTime = 0L
        scanFpsValue = 0f
        analysisResolution = ""
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

    @Suppress("DEPRECATION")
    private fun bindCameraUseCases() {
        val provider = cameraProvider ?: return

        val preview = Preview.Builder()
            .build()
            .also { it.surfaceProvider = previewView.surfaceProvider }

        imageAnalysis = ImageAnalysis.Builder()
            .setTargetResolution(Size(640, 480))
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
            if (currentQrType == QrType.RGB) {
                // RGB path: decode color QR canvases
                val decoder = RgbQrDecoder()
                val allChunks = mutableListOf<ChunkInfo>()
                for (uri in uris) {
                    try {
                        contentResolver.openInputStream(uri)?.use { stream ->
                            val bitmap = android.graphics.BitmapFactory.decodeStream(stream)
                            if (bitmap != null) {
                                val chunks = decoder.decodeImage(bitmap)
                                allChunks.addAll(chunks)
                                bitmap.recycle()
                            }
                        }
                    } catch (e: Exception) {
                        LogCollector.e(TAG, "RGB canvas decode failed: $uri", e)
                    }
                }

                withContext(Dispatchers.Main) {
                    loadingIndicator.visibility = View.GONE
                    if (allChunks.isNotEmpty()) {
                        processChunkList(allChunks)
                    } else {
                        showError("未在图片中检测到 RGB 二维码")
                    }
                }
            } else {
                // Mono path: use ML Kit directly
                // For chunked protocol, only scan the first image (phone can't scan
                // multiple QR codes simultaneously from canvas anyway)
                val allChunks = mutableListOf<ChunkInfo>()
                val rawContents = mutableListOf<String>()
                for (uri in uris) {
                    try {
                        val image = InputImage.fromFilePath(this@MainActivity, uri)
                        val barcodes = barcodeScanner.process(image).await()
                        for (barcode in barcodes) {
                            val raw = barcode.rawBytes
                            if (raw != null) {
                                val chunk = parsePayloadV2(raw)
                                if (chunk != null) {
                                    allChunks.add(chunk)
                                } else {
                                    // Not a chunked payload, treat as raw text
                                    val text = try {
                                        String(raw, Charsets.UTF_8)
                                    } catch (e: Exception) {
                                        raw.joinToString(" ") { "0x%02X".format(it) }
                                    }
                                    rawContents.add(text)
                                }
                            } else if (barcode.displayValue != null) {
                                rawContents.add(barcode.displayValue!!)
                            }
                        }
                        // Chunked protocol: only scan one image at a time
                        if (allChunks.isNotEmpty()) break
                    } catch (e: Exception) {
                        LogCollector.e(TAG, "图库图片解析失败: $uri", e)
                    }
                }

                withContext(Dispatchers.Main) {
                    loadingIndicator.visibility = View.GONE
                    when {
                        allChunks.isNotEmpty() -> {
                            // File chunks detected, process as file reception
                            processChunkList(allChunks)
                        }
                        rawContents.isNotEmpty() -> {
                            // Raw text only
                            onDetectRawFromGallery(rawContents)
                        }
                        else -> {
                            showError("未在图片中检测到二维码")
                        }
                    }
                }
            }
        }
    }

    private fun onDetectRawFromGallery(contents: List<String>) {
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

    private fun processImage(imageProxy: ImageProxy) {
        val now = System.currentTimeMillis()
        if (now - lastProcessTime < throttleMs) {
            imageProxy.close()
            return
        }
        lastProcessTime = now
        val submitTime = now

        val mediaImage = imageProxy.image ?: run {
            imageProxy.close()
            return
        }

        // Capture analysis resolution from first frame
        if (analysisResolution.isEmpty()) {
            analysisResolution = "${mediaImage.width}×${mediaImage.height}"
        }

        val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)

        barcodeScanner.process(image)
            .addOnSuccessListener { barcodes ->
                if (barcodes.isNotEmpty()) {
                    val elapsed = System.currentTimeMillis() - submitTime

                    // Track FPS
                    if (lastDetectionTime > 0) {
                        val interval = now - lastDetectionTime
                        scanFpsValue = (1000f / interval).coerceIn(0.1f, 60f)
                    }
                    lastDetectionTime = now
                    scanFps.text = "${analysisResolution}  扫描 %.1f fps  %dms".format(scanFpsValue, elapsed)
                    scanFps.visibility = View.VISIBLE

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
        showSaveLocation(outDir, outFile.name)
    }

    private fun showSaveLocation(outDir: File, fileName: String) {
        val locationText = "文件已保存到: ${outDir.absolutePath}/$fileName"
        // Show in result content area
        resultContent.visibility = View.VISIBLE
        resultContent.text = locationText
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

        // 按文件分组处理
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

        // 多文件：如果当前没有聚焦文件，聚焦到第一个活跃文件
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
            fileState.receivedCount = fileState.chunks.size
            hasNewChunk = true
        }

        if (hasNewChunk) {
            runOnUiThread { updateMultiFileProgress() }

            if (fileState.isComplete) {
                lifecycleScope.launch { assembleFile(fileState) }
            }
        }
    }

    // parsePayloadV2() moved to RgbQrDecoder.kt as a shared top-level function

    private fun showReceiving() {
        progressOverlay.visibility = View.VISIBLE
        detailPanel.visibility = View.VISIBLE
        scanHint.text = getScanHint()
        updateProgress()

        // 显示保存位置提示
        val outDir = SettingsActivity.getOutputDir(this)
        fileMetaText.text = "保存位置: ${outDir.absolutePath}"
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
        updateMultiFileProgress()
    }

    private fun updateMultiFileProgress() {
        val activeFiles = receiveManager.getActiveFiles()
        val completedFiles = receiveManager.getCompletedFiles()
        
        if (activeFiles.isEmpty() && completedFiles.isEmpty()) return

        // 显示总体进度
        val totalReceived = activeFiles.sumOf { it.receivedCount } + completedFiles.sumOf { it.totalChunks ?: 0 }
        val totalExpected = activeFiles.sumOf { it.totalChunks ?: 0 } + completedFiles.sumOf { it.totalChunks ?: 0 }
        val pct = if (totalExpected > 0) (totalReceived * 100 / totalExpected) else 0

        progressText.text = "$totalReceived/$totalExpected"
        progressBar.progress = pct
        progressPercent.text = "$pct%"

        // 显示当前文件信息
        val currentFile = activeFiles.firstOrNull() ?: completedFiles.lastOrNull()
        if (currentFile != null) {
            fileInfoText.text = currentFile.displayName
            val meta = StringBuilder("原始大小: ${formatBytes(currentFile.fileSize ?: 0)}")
            if (currentFile.isCompressed) meta.append(" · 7z压缩")
            fileMetaText.text = meta.toString()

            // chunk 状态
            val total = currentFile.totalChunks ?: 0
            val receivedIds = currentFile.chunks.keys.sorted()
            val missingIds = (0 until total).filter { it !in currentFile.chunks }

            receivedChunksText.text = "已收到 (${receivedIds.size}): ${receivedIds.truncate(15)}"
            if (missingIds.isEmpty()) {
                missingChunksText.visibility = View.GONE
            } else {
                missingChunksText.visibility = View.VISIBLE
                missingChunksText.text = "缺失 (${missingIds.size}): ${missingIds.truncate(15)}"
            }
        }
    }

    private fun List<Int>.truncate(max: Int): String {
        return if (size <= max) joinToString(", ")
        else "${take(max).joinToString(", ")}... 等${size}块"
    }

    private suspend fun assembleFile(fileState: FileReceiveState) {
        if (fileState.appState == AppState.ASSEMBLING) return
        fileState.appState = AppState.ASSEMBLING

        withContext(Dispatchers.IO) {
            try {
                val sortedKeys = fileState.chunks.keys.sorted()
                val fullData = mutableListOf<Byte>()
                for (key in sortedKeys) {
                    fullData.addAll(fileState.chunks[key]!!.toList())
                }
                var data = fullData.toByteArray()

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
                    withContext(Dispatchers.Main) {
                        updateMultiFileProgress()
                    }
                    return@withContext
                }

                // 7z decompression (must happen before CRC32/size checks)
                if (fileState.isCompressed) {
                    LogCollector.i(TAG, "[${fileState.fileKey}] Decompressing 7z data (${data.size} bytes)")
                    val decompressed = decompress7z(data)
                    if (decompressed == null) {
                        fileState.appState = AppState.ERROR
                        fileState.lastError = "7z 解压失败"
                        withContext(Dispatchers.Main) {
                            updateMultiFileProgress()
                        }
                        return@withContext
                    }
                    LogCollector.i(TAG, "[${fileState.fileKey}] Decompressed: ${decompressed.size} bytes")
                    data = decompressed
                }

                // File size verification
                if (fileState.fileSize != null && data.size != fileState.fileSize) {
                    LogCollector.w(TAG, "[${fileState.fileKey}] File size mismatch: expected=${fileState.fileSize}, actual=${data.size}")
                    fileState.appState = AppState.ERROR
                    fileState.lastError = "文件大小不匹配: 期望 ${fileState.fileSize}, 实际 ${data.size}"
                    withContext(Dispatchers.Main) {
                        updateMultiFileProgress()
                    }
                    return@withContext
                }

                // CRC32 verification (on decompressed data)
                val expectedCrc = fileState.fileCrc32
                if (expectedCrc != null) {
                    val crc = CRC32()
                    crc.update(data)
                    val actualCrc = crc.value
                    if (actualCrc != expectedCrc) {
                        LogCollector.w(TAG, "[${fileState.fileKey}] CRC32 mismatch: expected=$expectedCrc, actual=$actualCrc")
                        fileState.appState = AppState.ERROR
                        fileState.lastError = "CRC32 校验失败"
                        withContext(Dispatchers.Main) {
                            updateMultiFileProgress()
                        }
                        return@withContext
                    }
                    LogCollector.i(TAG, "[${fileState.fileKey}] CRC32 verified")
                }

                fileState.outputSize = data.size

                val outName = if (!fileState.fileName.isNullOrEmpty()) {
                    fileState.fileName!!
                } else {
                    detectExtension(data)
                }

                // Don't write file yet — show save dialog first
                pendingData = data
                pendingFileName = outName
                pendingFileKey = fileState.fileKey

                fileState.appState = AppState.DONE
                LogCollector.i(TAG, "[${fileState.fileKey}] File assembled: $outName (${formatBytes(data.size)})")

                withContext(Dispatchers.Main) {
                    stopCamera()
                    updateMultiFileProgress()
                    showSaveDialog(outName, data.size)
                }
            } catch (e: Exception) {
                LogCollector.e(TAG, "[$fileState.fileKey] 文件组装失败", e)
                fileState.appState = AppState.ERROR
                fileState.lastError = e.message
                withContext(Dispatchers.Main) {
                    updateMultiFileProgress()
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
            val buf = ByteArray(8192)
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

    private fun showDone() {
        loadingIndicator.visibility = View.GONE
        progressOverlay.visibility = View.GONE
        detailPanel.visibility = View.GONE
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
        progressOverlay.visibility = View.GONE
        detailPanel.visibility = View.GONE
        errorPanel.visibility = View.VISIBLE
        errorText.text = message
        btnContinue.visibility = if (showContinue) View.VISIBLE else View.GONE
    }

    private fun showSaveDialog(fileName: String, fileSize: Int) {
        val data = pendingData ?: return
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
                pendingData = null
                pendingFileName = null
                pendingFileKey = null
            }
            .setCancelable(false)
            .show()
    }

    private fun saveToDefaultPath() {
        val data = pendingData ?: return
        val outName = pendingFileName ?: return
        val fileKey = pendingFileKey ?: return

        val outDir = SettingsActivity.getOutputDir(this)
        if (!outDir.exists()) outDir.mkdirs()

        val outFile = File(outDir, outName)
        outFile.writeBytes(data)

        val fileState = receiveManager.get(fileKey)
        fileState?.outputPath = outFile.absolutePath

        pendingData = null
        pendingFileName = null
        pendingFileKey = null

        Toast.makeText(this, "已保存到: ${outFile.absolutePath}", Toast.LENGTH_LONG).show()
        showDone()
    }

    private fun saveToChosenUri(uri: Uri) {
        val data = pendingData ?: return
        val fileKey = pendingFileKey ?: return

        try {
            contentResolver.openOutputStream(uri)?.use { output ->
                output.write(data)
            }
            val fileState = receiveManager.get(fileKey)
            fileState?.outputPath = uri.toString()

            pendingData = null
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
        
        if (completedFiles.size == 1) {
            val path = completedFiles[0].outputPath ?: return
            val file = File(path)
            val uri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, getMimeType(file))
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(Intent.createChooser(intent, "打开文件"))
        } else {
            // 多文件：打开输出目录
            val outDir = SettingsActivity.getOutputDir(this)
            val uri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", outDir)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "resource/folder")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(Intent.createChooser(intent, "打开文件夹"))
        }
    }

    private fun shareFile() {
        val completedFiles = receiveManager.getCompletedFiles()
        if (completedFiles.isEmpty()) return
        
        if (completedFiles.size == 1) {
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
        } else {
            // 多文件分享
            val uris = ArrayList<Uri>()
            for (fileState in completedFiles) {
                val path = fileState.outputPath ?: continue
                val file = File(path)
                uris.add(FileProvider.getUriForFile(this, "${packageName}.fileprovider", file))
            }
            val intent = Intent(Intent.ACTION_SEND_MULTIPLE).apply {
                type = "*/*"
                putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris)
                putExtra(Intent.EXTRA_TEXT, "通过 QR 码接收的 ${completedFiles.size} 个文件")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(Intent.createChooser(intent, "分享文件"))
        }
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
        // Return to main interface from receiving state
        receiveManager.clear()
        currentFileKey = null
        receiveState = ReceiveState()
        resultPanel.visibility = View.GONE
        errorPanel.visibility = View.GONE
        progressOverlay.visibility = View.GONE
        detailPanel.visibility = View.GONE
        loadingIndicator.visibility = View.GONE
        previewView.visibility = View.GONE
        scanFrame.visibility = View.GONE
        scanHint.visibility = View.GONE
        scanFps.visibility = View.GONE
        sourcePanel.visibility = View.VISIBLE
        stopCamera()
    }

    private fun reset() {
        receiveManager.clear()
        currentFileKey = null
        receiveState = ReceiveState()
        resultPanel.visibility = View.GONE
        errorPanel.visibility = View.GONE
        progressOverlay.visibility = View.GONE
        detailPanel.visibility = View.GONE
        loadingIndicator.visibility = View.GONE

        previewView.visibility = View.GONE
        scanFrame.visibility = View.GONE
        scanHint.visibility = View.GONE
        scanFps.visibility = View.GONE
        sourcePanel.visibility = View.VISIBLE

        stopCamera()
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
        startCameraMode()
    }

    private fun stopCamera() {
        imageAnalysis?.clearAnalyzer()
        cameraProvider?.unbindAll()
    }

    private fun formatBytes(bytes: Int): String {
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

// await() extension moved to RgbQrDecoder.kt as a shared top-level function
