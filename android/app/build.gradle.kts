plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "co.dapx.cuadrame.captura"
    compileSdk = 35

    defaultConfig {
        applicationId = "co.dapx.cuadrame.captura"
        minSdk = 26 // Android 8.0 en adelante
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }

    // La llave de firma vive FUERA del repositorio (DAPX/.secretos). Se pasa por variables de entorno:
    //   ANDROID_KEYSTORE, ANDROID_KEY_ALIAS, ANDROID_KEYSTORE_PASSWORD
    // Sin ellas, la compilación de lanzamiento queda sin firmar (y la de depuración usa la llave de depuración).
    val rutaLlave = System.getenv("ANDROID_KEYSTORE")
    if (!rutaLlave.isNullOrBlank()) {
        signingConfigs {
            create("lanzamiento") {
                storeFile = file(rutaLlave)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (!rutaLlave.isNullOrBlank()) signingConfig = signingConfigs.getByName("lanzamiento")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

// Solo dos librerías de AndroidX (la base de Android); nada de terceros ni de seguimiento.
dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
