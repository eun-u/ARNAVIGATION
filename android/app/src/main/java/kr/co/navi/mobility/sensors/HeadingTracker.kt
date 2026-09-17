package kr.co.navi.mobility.sensors

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

sealed interface HeadingState {
    data object Waiting : HeadingState
    data object Unavailable : HeadingState
    data class Available(val degrees: Float) : HeadingState
}

class HeadingTracker(context: Context) : SensorEventListener {
    private val manager = context.applicationContext
        .getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val rotationSensor = manager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
    private val mutableState = MutableStateFlow<HeadingState>(HeadingState.Waiting)
    val state: StateFlow<HeadingState> = mutableState.asStateFlow()

    fun start() {
        val sensor = rotationSensor
        if (sensor == null) {
            mutableState.value = HeadingState.Unavailable
            return
        }
        manager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_UI)
    }

    fun stop() {
        manager.unregisterListener(this)
        mutableState.value = HeadingState.Waiting
    }

    override fun onSensorChanged(event: SensorEvent) {
        val rotation = FloatArray(9)
        val orientation = FloatArray(3)
        SensorManager.getRotationMatrixFromVector(rotation, event.values)
        SensorManager.getOrientation(rotation, orientation)
        val degrees = Math.toDegrees(orientation[0].toDouble()).toFloat()
        mutableState.value = HeadingState.Available((degrees + 360f) % 360f)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
}
