package com.pisces312.qrcast

import android.Manifest
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : AppCompatActivity() {

    private lateinit var qrTypeGroup: RadioGroup
    private lateinit var protocolGroup: RadioGroup
    private lateinit var sourcePanel: ScrollView

    private val barcodeScanner: BarcodeScanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .build()
    )

    private var currentMode = ScanMode.CHUNKED
    private var currentQrType = QrType.MONO

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            launchScanActivity()
        } else {
            Toast.makeText(this, "需要相机权限才能扫描QR码", Toast.LENGTH_SHORT).show()
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

        val prefs = getSharedPreferences(SettingsActivity.PREFS_NAME, MODE_PRIVATE)
        if (prefs.getBoolean(SettingsActivity.KEY_LANDSCAPE, false)) {
            requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
        }

        setContentView(R.layout.activity_main)
        initViews()
    }

    override fun onResume() {
        super.onResume()
        val prefs = getSharedPreferences(SettingsActivity.PREFS_NAME, MODE_PRIVATE)
        if (prefs.getBoolean(SettingsActivity.KEY_KEEP_SCREEN_ON, false)) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    private fun initViews() {
        qrTypeGroup = findViewById(R.id.qrTypeGroup)
        protocolGroup = findViewById(R.id.protocolGroup)
        sourcePanel = findViewById(R.id.sourcePanel)

        findViewById<LinearLayout>(R.id.btnCamera).setOnClickListener { onCameraSelected() }
        findViewById<LinearLayout>(R.id.btnGallery).setOnClickListener { onGallerySelected() }
        findViewById<ImageButton>(R.id.btnSettings).setOnClickListener { openSettings() }
        findViewById<ImageButton>(R.id.btnLogs).setOnClickListener { openLogs() }
        findViewById<ImageButton>(R.id.btnHelp).setOnClickListener { openHelp() }

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
                launchScanActivity()
            }
            shouldShowRequestPermissionRationale(Manifest.permission.CAMERA) -> {
                requestPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
            else -> {
                requestPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }

    private fun launchScanActivity() {
        val intent = Intent(this, ScanActivity::class.java).apply {
            putExtra(ScanActivity.EXTRA_QR_TYPE, currentQrType.ordinal)
            putExtra(ScanActivity.EXTRA_SCAN_MODE, currentMode.ordinal)
        }
        startActivity(intent)
    }

    private fun onGallerySelected() {
        LogCollector.i(TAG, "用户选择图库选图，模式: $currentMode")
        openDocumentLauncher.launch(arrayOf("image/*"))
    }

    private fun processGalleryImages(uris: List<Uri>) {
        if (uris.isEmpty()) return

        lifecycleScope.launch(Dispatchers.IO) {
            if (currentQrType == QrType.RGB) {
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
                    if (allChunks.isNotEmpty()) {
                        // TODO: Navigate to result or scan activity with gallery chunks
                        Toast.makeText(this@MainActivity, "检测到 ${allChunks.size} 个RGB数据块", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(this@MainActivity, "未在图片中检测到 RGB 二维码", Toast.LENGTH_SHORT).show()
                    }
                }
            } else {
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
                        if (allChunks.isNotEmpty()) break
                    } catch (e: Exception) {
                        LogCollector.e(TAG, "图库图片解析失败: $uri", e)
                    }
                }

                withContext(Dispatchers.Main) {
                    when {
                        allChunks.isNotEmpty() -> {
                            Toast.makeText(this@MainActivity, "检测到 ${allChunks.size} 个数据块", Toast.LENGTH_SHORT).show()
                            // TODO: Navigate to result or scan activity with gallery chunks
                        }
                        rawContents.isNotEmpty() -> {
                            // Save raw text directly
                            val outDir = SettingsActivity.getOutputDir(this@MainActivity)
                            if (!outDir.exists()) outDir.mkdirs()
                            val outFile = File(outDir, SettingsActivity.generateTimestampFileName("txt"))
                            outFile.writeText(rawContents.joinToString("\n\n---\n\n"))
                            Toast.makeText(this@MainActivity, "已保存: ${outFile.name}", Toast.LENGTH_LONG).show()
                        }
                        else -> {
                            Toast.makeText(this@MainActivity, "未在图片中检测到二维码", Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            }
        }
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

    override fun onDestroy() {
        super.onDestroy()
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

data class ChunkInfo(
    val seq: Int,
    val total: Int,
    val payload: ByteArray,
    val fileName: String? = null,
    val fileCrc32: Long? = null,
    val fileSize: Long? = null,
    val isCompressed: Boolean = false
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is ChunkInfo) return false
        return seq == other.seq && total == other.total && payload.contentEquals(other.payload)
    }
    override fun hashCode(): Int = 31 * (31 * seq + total) + payload.contentHashCode()
}
