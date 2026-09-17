package kr.co.navi.mobility

import android.content.Context
import kr.co.navi.mobility.data.NaviSessionStore
import kr.co.navi.mobility.data.remote.NaviApiClient
import kr.co.navi.mobility.data.repository.NaviRepository
import kr.co.navi.mobility.data.repository.NetworkNaviRepository
import kr.co.navi.mobility.location.LocationTracker
import kr.co.navi.mobility.sensors.HeadingTracker

class NaviAppContainer(context: Context) {
    val sessionStore = NaviSessionStore()
    val repository: NaviRepository = NetworkNaviRepository(
        NaviApiClient(BuildConfig.BACKEND_BASE_URL),
    )
    val locationTracker = LocationTracker(context)
    val headingTracker = HeadingTracker(context)
}
