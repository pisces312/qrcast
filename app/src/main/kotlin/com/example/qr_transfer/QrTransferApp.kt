package com.example.qr_transfer

import android.app.Application

class QrTransferApp : Application() {

    override fun onCreate() {
        super.onCreate()
        LogCollector.init(this)
    }
}
