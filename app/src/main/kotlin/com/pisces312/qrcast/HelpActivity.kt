package com.pisces312.qrcast

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class HelpActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_help)

        findViewById<TextView>(R.id.helpContent).text = getHelpText()
    }

    private fun getHelpText(): String {
        return """
QRCast 使用说明

【基本功能】
QRCast 是一款通过二维码传输文件的工具，支持黑白二维码和 RGB 彩色二维码两种模式。

【二维码类型】
• 黑白二维码：标准二维码，兼容性好，但单张容量有限
• RGB 彩色二维码：将数据拆分为红/绿/蓝三个通道，单张可传输更多数据

【数据模式】
• 分块协议：大文件自动拆分为多个二维码分块传输
• 原始数据：直接显示二维码中的原始文本内容

【使用方法】
1. 选择二维码来源：相机实时扫描或从图库选择图片
2. 对准二维码或选择包含二维码的图片
3. 自动识别并接收数据
4. 接收完成后可打开或分享文件

【多文件接收】
• 支持同时接收多个文件
• 从不同图片中扫描的二维码会自动按文件名分组
• 每个文件独立显示进度

【提示】
• 确保二维码清晰可见，光线充足
• 彩色二维码需要保持颜色准确，避免过度压缩
• 大文件建议使用分块协议，分多张二维码传输
        """.trimIndent()
    }
}
