# ─── Flutter 核心规则 ──────────────────────────────────────────────────────
# 保留 Flutter 引擎和框架相关的类
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# ─── mobile_scanner 原生库保护 ─────────────────────────────────────────────
# 保持 ML Kit / ZXing 相关类不被混淆（虽然通常不需要，但为了安全）
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.** { *; }

# ─── open_filex 文件打开保护 ───────────────────────────────────────────────
-keep class com.crazecoder.openfile.** { *; }

# ─── share_plus 分享保护 ───────────────────────────────────────────────────
-keep class dev.fluttercommunity.plus.share.** { *; }

# ─── path_provider 保护 ───────────────────────────────────────────────────
-keep class io.flutter.plugins.pathprovider.** { *; }

# ─── permission_handler 保护 ──────────────────────────────────────────────
-keep class com.baseflow.permissionhandler.** { *; }

# ─── 通用规则 ──────────────────────────────────────────────────────────────
# 保持 Parcelable 实现不被破坏
-keep class * implements android.os.Parcelable {
  public static final android.os.Parcelable$Creator *;
}

# 保持 Serializable 实现
-keep class * implements java.io.Serializable

# ─── 忽略 Google Play Core 缺失类（解决 R8 报错） ──────────────────────────
-dontwarn com.google.android.play.core.**

# ─── 补充 Flutter 引擎可能引用的缺失类 ─────────────────────────────────────
-dontwarn io.flutter.embedding.engine.deferredcomponents.**

# 保持 Native 方法签名
-keepclasseswithmembernames,includedescriptorclasses class * {
    native <methods>;
}

