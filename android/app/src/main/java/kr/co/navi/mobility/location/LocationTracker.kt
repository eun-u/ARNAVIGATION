package kr.co.navi.mobility.location

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import androidx.core.content.ContextCompat
import kr.co.navi.mobility.data.model.CoordinateDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

sealed interface LocationState {
    data object Waiting : LocationState
    data object PermissionMissing : LocationState
    data object ProviderUnavailable : LocationState
    data class Available(
        val coordinate: CoordinateDto,
        val accuracyMeters: Float?,
        val observedAtMillis: Long,
    ) : LocationState
}

class LocationTracker(context: Context) : LocationListener {
    private val appContext = context.applicationContext
    private val manager = appContext.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private val mutableState = MutableStateFlow<LocationState>(LocationState.Waiting)
    val state: StateFlow<LocationState> = mutableState.asStateFlow()

    fun start() {
        val fine = ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.ACCESS_COARSE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        if (!fine && !coarse) {
            mutableState.value = LocationState.PermissionMissing
            return
        }
        var registered = false
        listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER).forEach { provider ->
            if (runCatching { manager.isProviderEnabled(provider) }.getOrDefault(false)) {
                runCatching {
                    manager.requestLocationUpdates(provider, 1_000L, 1f, this)
                    manager.getLastKnownLocation(provider)?.let(::publish)
                    registered = true
                }
            }
        }
        if (!registered) mutableState.value = LocationState.ProviderUnavailable
    }

    fun stop() {
        runCatching { manager.removeUpdates(this) }
        mutableState.value = LocationState.Waiting
    }

    override fun onLocationChanged(location: Location) = publish(location)

    private fun publish(location: Location) {
        mutableState.value = LocationState.Available(
            coordinate = CoordinateDto(lat = location.latitude, lon = location.longitude),
            accuracyMeters = location.accuracy.takeIf { location.hasAccuracy() },
            observedAtMillis = location.time,
        )
    }

    @Deprecated("Required for older Android location providers")
    override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) = Unit
}
