package com.pisces312.qrcast

import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.view.MenuItem
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class SettingsActivity : AppCompatActivity() {

    private lateinit var tvCurrentDir: TextView
    private lateinit var etOutputDir: EditText
    private lateinit var btnBrowse: Button
    private lateinit var btnSave: Button
    private lateinit var btnReset: Button
    private lateinit var switchKeepScreenOn: SwitchCompat
    private lateinit var switchLandscape: SwitchCompat

    private val dirPickerLauncher = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.OpenDocumentTree()
    ) { uri ->
        uri?.let {
            contentResolver.takePersistableUriPermission(
                it,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
            val path = it.toString()
            etOutputDir.setText(path)
            tvCurrentDir.text = "当前: $path"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        supportActionBar?.title = "设置"

        tvCurrentDir = findViewById(R.id.tvCurrentDir)
        etOutputDir = findViewById(R.id.etOutputDir)
        btnBrowse = findViewById(R.id.btnBrowse)
        btnSave = findViewById(R.id.btnSave)
        btnReset = findViewById(R.id.btnReset)
        switchKeepScreenOn = findViewById(R.id.switchKeepScreenOn)
        switchLandscape = findViewById(R.id.switchLandscape)

        loadSettings()

        btnBrowse.setOnClickListener { pickDirectory() }
        btnSave.setOnClickListener { saveSettings() }
        btnReset.setOnClickListener { resetSettings() }

        switchKeepScreenOn.setOnCheckedChangeListener { _, isChecked ->
            getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_KEEP_SCREEN_ON, isChecked)
                .apply()
        }

        switchLandscape.setOnCheckedChangeListener { _, isChecked ->
            getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_LANDSCAPE, isChecked)
                .apply()
        }
    }

    private fun loadSettings() {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val savedDir = prefs.getString(KEY_OUTPUT_DIR, null)
        val defaultDir = getDefaultOutputDir(this).absolutePath

        tvCurrentDir.text = "当前: ${savedDir ?: defaultDir}"
        etOutputDir.setText(savedDir ?: defaultDir)
        switchKeepScreenOn.isChecked = prefs.getBoolean(KEY_KEEP_SCREEN_ON, false)
        switchLandscape.isChecked = prefs.getBoolean(KEY_LANDSCAPE, false)
    }

    private fun pickDirectory() {
        dirPickerLauncher.launch(null)
    }

    private fun saveSettings() {
        val dir = etOutputDir.text.toString().trim()
        if (dir.isEmpty()) {
            Toast.makeText(this, "目录不能为空", Toast.LENGTH_SHORT).show()
            return
        }

        getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_OUTPUT_DIR, dir)
            .apply()

        tvCurrentDir.text = "当前: $dir"
        Toast.makeText(this, "设置已保存", Toast.LENGTH_SHORT).show()
        LogCollector.i(TAG, "输出目录已修改为: $dir")
    }

    private fun resetSettings() {
        AlertDialog.Builder(this)
            .setTitle("恢复默认")
            .setMessage("确定要恢复默认输出目录吗？")
            .setPositiveButton("确定") { _, _ ->
                getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    .edit()
                    .remove(KEY_OUTPUT_DIR)
                    .apply()
                val defaultDir = getDefaultOutputDir(this@SettingsActivity).absolutePath
                tvCurrentDir.text = "当前: $defaultDir"
                etOutputDir.setText(defaultDir)
                Toast.makeText(this, "已恢复默认", Toast.LENGTH_SHORT).show()
                LogCollector.i(TAG, "输出目录已恢复默认: $defaultDir")
            }
            .setNegativeButton("取消", null)
            .show()
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            android.R.id.home -> {
                finish()
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    companion object {
        private const val TAG = "Settings"
        const val PREFS_NAME = "qr_transfer_settings"
        const val KEY_OUTPUT_DIR = "output_directory"
        const val KEY_KEEP_SCREEN_ON = "keep_screen_on"
        const val KEY_LANDSCAPE = "landscape_mode"

        fun getDefaultOutputDir(context: Context): File {
            return File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "QRCast")
        }

        fun getOutputDir(context: Context): File {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val savedDir = prefs.getString(KEY_OUTPUT_DIR, null)
            return if (savedDir != null) {
                File(savedDir)
            } else {
                getDefaultOutputDir(context)
            }
        }

        fun generateTimestampFileName(extension: String = "txt"): String {
            val sdf = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.getDefault())
            return "${sdf.format(Date())}.$extension"
        }
    }
}
