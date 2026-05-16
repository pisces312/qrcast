package com.example.qr_transfer

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

class LogActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_log)

        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        supportActionBar?.title = getString(R.string.title_logs)

        findViewById<android.widget.ImageButton>(R.id.fabScrollBottom).setOnClickListener {
            val scrollView = findViewById<android.widget.ScrollView>(R.id.logScrollView)
            scrollView.post {
                scrollView.fullScroll(android.view.View.FOCUS_DOWN)
            }
        }

        loadLogs()
    }

    private fun loadLogs() {
        val logTextView = findViewById<android.widget.TextView>(R.id.logTextView)
        val logs = StringBuilder()

        val fileLogs = LogCollector.getFileLogs()
        if (fileLogs.isNotEmpty()) {
            logs.append(fileLogs)
        } else {
            LogCollector.getMemoryLogs().forEach {
                logs.appendLine(it.format())
            }
        }

        logTextView.text = logs.toString()

        val scrollView = findViewById<android.widget.ScrollView>(R.id.logScrollView)
        scrollView.post {
            scrollView.fullScroll(android.view.View.FOCUS_DOWN)
        }
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_log, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            android.R.id.home -> {
                finish()
                true
            }
            R.id.action_copy -> {
                copyLogs()
                true
            }
            R.id.action_share -> {
                shareLogs()
                true
            }
            R.id.action_clear -> {
                clearLogs()
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    private fun copyLogs() {
        val logs = findViewById<android.widget.TextView>(R.id.logTextView).text.toString()
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("QRTransfer Logs", logs))
        Toast.makeText(this, R.string.logs_copied, Toast.LENGTH_SHORT).show()
    }

    private fun shareLogs() {
        val logs = findViewById<android.widget.TextView>(R.id.logTextView).text.toString()
        val shareIntent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(android.content.Intent.EXTRA_SUBJECT, "QRTransfer 日志")
            putExtra(android.content.Intent.EXTRA_TEXT, logs)
        }
        startActivity(android.content.Intent.createChooser(shareIntent, getString(R.string.share_logs)))
    }

    private fun clearLogs() {
        AlertDialog.Builder(this)
            .setTitle(R.string.clear_logs_title)
            .setMessage(R.string.clear_logs_confirm)
            .setPositiveButton(R.string.yes) { _, _ ->
                LogCollector.clearLogs()
                findViewById<android.widget.TextView>(R.id.logTextView).text = ""
                Toast.makeText(this, R.string.logs_cleared, Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton(R.string.no, null)
            .show()
    }
}
