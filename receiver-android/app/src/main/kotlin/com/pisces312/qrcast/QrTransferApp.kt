package com.pisces312.qrcast

import android.app.Application

class QrTransferApp : Application() {

    override fun onCreate() {
        super.onCreate()
        LogCollector.init(this)
    }

    override fun onTerminate() {
        LogCollector.shutdown()
        super.onTerminate()
    }
}
