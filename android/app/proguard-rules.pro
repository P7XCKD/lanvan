# ============================================================
# Lanvan ProGuard / R8 Rules
# ============================================================

# ---------- Chaquopy (Python Bridge) ----------
# Chaquopy relies heavily on JNI and reflection -- never strip or rename
-keep class com.chaquo.** { *; }
-keep interface com.chaquo.** { *; }
-dontwarn com.chaquo.**

# Keep all classes accessed by Python proxy layer
-keepclassmembers class * {
    @com.chaquo.python.PyObject *;
}

# ---------- Android App Components ----------
-keep public class * extends android.app.Activity
-keep public class * extends android.app.Service
-keep public class * extends android.content.BroadcastReceiver
-keep public class * extends android.content.ContentProvider

# Keep our specific components by name (extra safety)
-keep class com.lanvan.app.MainActivity { *; }
-keep class com.lanvan.app.ServerService { *; }

# ---------- Kotlin Metadata ----------
-keep class kotlin.Metadata { *; }
-keepclassmembers class ** { *; }
-keepattributes *Annotation*, InnerClasses
-keepattributes Signature
-keepattributes Exceptions
-keepattributes SourceFile, LineNumberTable

# ---------- AndroidX / AppCompat ----------
-keep class androidx.** { *; }
-dontwarn androidx.**

# ---------- Suppress common warnings ----------
-dontwarn org.python.**
-dontwarn sun.misc.**
-dontwarn java.lang.invoke.**
-dontwarn okhttp3.**
-dontwarn okio.**
