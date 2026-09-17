package kr.co.navi.mobility

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import kr.co.navi.mobility.ui.NaviApp
import kr.co.navi.mobility.ui.theme.NaviTheme
import org.maplibre.android.MapLibre

class MainActivity : ComponentActivity() {
    private lateinit var container: NaviAppContainer

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // The app uses MapLibre's OpenGL artifact for broad device/emulator compatibility.
        MapLibre.getInstance(this)
        container = NaviAppContainer(applicationContext)
        enableEdgeToEdge()
        setContent {
            NaviTheme {
                NaviApp(container)
            }
        }
    }
}
