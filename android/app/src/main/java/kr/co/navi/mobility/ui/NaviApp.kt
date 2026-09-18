package kr.co.navi.mobility.ui

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import kr.co.navi.mobility.NaviAppContainer
import kr.co.navi.mobility.ui.components.NaviBottomBar
import kr.co.navi.mobility.ui.components.NaviDestinations
import kr.co.navi.mobility.ui.screens.FrontendCameraScreen
import kr.co.navi.mobility.ui.screens.FrontendArrivalScreen
import kr.co.navi.mobility.ui.screens.FrontendExplainScreen
import kr.co.navi.mobility.ui.screens.FrontendHomeScreen
import kr.co.navi.mobility.ui.screens.FrontendMapNavigationScreen
import kr.co.navi.mobility.ui.screens.FrontendMobilityProfileScreen
import kr.co.navi.mobility.ui.screens.FrontendOnboardingScreen
import kr.co.navi.mobility.ui.screens.FrontendPlanScreen
import kr.co.navi.mobility.ui.screens.FrontendPermissionScreen
import kr.co.navi.mobility.ui.screens.FrontendRerouteScreen
import kr.co.navi.mobility.ui.screens.FrontendReportScreen
import kr.co.navi.mobility.ui.screens.FrontendRouteResultScreen
import kr.co.navi.mobility.ui.screens.FrontendSavedScreen
import kr.co.navi.mobility.ui.screens.FrontendSearchScreen
import kr.co.navi.mobility.ui.screens.FrontendSettingsScreen
import kr.co.navi.mobility.ui.screens.FrontendSplashScreen
import kr.co.navi.mobility.ui.screens.GraphCandidateScreen
import kotlinx.coroutines.flow.collect

/**
 * 상시 목적지 4개(홈 · 길찾기 · 제보 · 내 정보) 위에
 * 안내 흐름이 전체화면으로 덮이는 구조.
 *
 * 탭 전환은 각 탭의 백스택을 보존하고, 안내(경로 결과 · 지도 · AR · 제보 작성 · 도착)는
 * 탭바를 가린다. 자세한 규칙은 docs/screen_state_matrix.md 참고.
 */
private object NaviRoute {
    const val Splash = "splash"
    const val Onboarding = "onboarding"
    const val Permission = "permission"
    const val Mobility = "mobility"

    const val Home = "home"
    const val Search = "search"
    const val Saved = "saved"
    const val Settings = "settings"
    const val Plan = "plan"

    const val Route = "route"
    const val Explain = "explain"
    const val GraphCandidates = "graph-candidates"
    const val Navigation = "navigation"
    const val Camera = "camera"
    const val ReportForm = "report-form"
    const val Reroute = "reroute"
    const val Arrival = "arrival"
}

@Composable
fun NaviApp(container: NaviAppContainer) {
    val navController = rememberNavController()
    val locationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) {
        navController.navigate(NaviRoute.Mobility) { launchSingleTop = true }
    }
    val planViewModel: PlanViewModel = viewModel(
        key = "navi-plan",
        factory = NaviViewModelFactory {
            PlanViewModel(
                repository = container.repository,
                sessionStore = container.sessionStore,
                locationTracker = container.locationTracker,
            )
        },
    )
    val routeViewModel: RouteViewModel = viewModel(
        key = "navi-route",
        factory = NaviViewModelFactory { RouteViewModel(container.sessionStore) },
    )
    val navigationViewModel: NavigationViewModel = viewModel(
        key = "navi-navigation",
        factory = NaviViewModelFactory {
            NavigationViewModel(
                repository = container.repository,
                sessionStore = container.sessionStore,
                locationTracker = container.locationTracker,
                headingTracker = container.headingTracker,
            )
        },
    )

    val session by routeViewModel.sessionState.collectAsStateWithLifecycle()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route ?: NaviRoute.Splash
    val tabRoutes = NaviDestinations.map { it.route }
    val showBottomBar = currentRoute in tabRoutes && currentRoute != NaviRoute.Search

    fun selectTab(route: String) {
        navController.navigate(route) {
            popUpTo(NaviRoute.Home) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    fun openHomeClearingEntryFlow() {
        if (navController.popBackStack(NaviRoute.Home, false)) return
        navController.navigate(NaviRoute.Home) {
            popUpTo(NaviRoute.Onboarding) { inclusive = true }
            launchSingleTop = true
        }
    }

    fun stopGuidance() {
        container.sessionStore.clearJourney()
        navController.navigate(NaviRoute.Home) {
            popUpTo(NaviRoute.Home) { inclusive = false }
            launchSingleTop = true
        }
    }

    LaunchedEffect(navigationViewModel, navController) {
        navigationViewModel.arrivalEvents.collect {
            navController.navigate(NaviRoute.Arrival) {
                launchSingleTop = true
                popUpTo(NaviRoute.Navigation) { inclusive = true }
            }
        }
    }

    Column(Modifier.fillMaxSize()) {
        Box(Modifier.weight(1f)) {
            NavHost(
                navController = navController,
                startDestination = NaviRoute.Splash,
            ) {
                composable(NaviRoute.Splash) {
                    FrontendSplashScreen(
                        onFinished = {
                            navController.navigate(NaviRoute.Onboarding) {
                                popUpTo(NaviRoute.Splash) { inclusive = true }
                            }
                        },
                    )
                }
                composable(NaviRoute.Onboarding) {
                    FrontendOnboardingScreen(
                        onSkip = ::openHomeClearingEntryFlow,
                        onNext = { navController.navigate(NaviRoute.Permission) },
                    )
                }
                composable(NaviRoute.Permission) {
                    FrontendPermissionScreen(
                        onBack = { navController.popBackStack() },
                        onContinue = {
                            locationPermissionLauncher.launch(
                                arrayOf(
                                    Manifest.permission.ACCESS_FINE_LOCATION,
                                    Manifest.permission.ACCESS_COARSE_LOCATION,
                                ),
                            )
                        },
                        onLater = { navController.navigate(NaviRoute.Mobility) },
                    )
                }
                composable(NaviRoute.Mobility) {
                    FrontendMobilityProfileScreen(
                        initialProfile = session.profile,
                        onBack = { navController.popBackStack() },
                        onStart = { profile ->
                            planViewModel.setProfile(profile)
                            openHomeClearingEntryFlow()
                        },
                    )
                }

                // ── 상시 목적지 ────────────────────────────────────────────
                composable(NaviRoute.Home) {
                    FrontendHomeScreen(
                        session = session,
                        onSearch = { selectTab(NaviRoute.Search) },
                        onActiveGuidance = {
                            navController.navigate(
                                if (session.activeRoute != null) NaviRoute.Navigation else NaviRoute.Search,
                            )
                        },
                        onEditProfile = { navController.navigate(NaviRoute.Mobility) },
                        onSettings = { selectTab(NaviRoute.Settings) },
                    )
                }
                composable(NaviRoute.Search) {
                    FrontendSearchScreen(
                        onBack = { navController.popBackStack() },
                        onDestinationSelected = { navController.navigate(NaviRoute.Plan) },
                    )
                }
                composable(NaviRoute.Saved) {
                    FrontendSavedScreen(
                        onBack = { navController.popBackStack() },
                        onOpenReport = { navController.navigate(NaviRoute.ReportForm) },
                    )
                }
                composable(NaviRoute.Settings) {
                    FrontendSettingsScreen(
                        session = session,
                        onEditProfile = { navController.navigate(NaviRoute.Mobility) },
                    )
                }
                composable(NaviRoute.Plan) {
                    FrontendPlanScreen(
                        viewModel = planViewModel,
                        onBack = { navController.popBackStack() },
                        onEditProfile = { navController.navigate(NaviRoute.Mobility) },
                        onRouteReady = { navController.navigate(NaviRoute.Route) },
                    )
                }

                // ── 안내 흐름 · 탭바를 덮는다 ──────────────────────────────
                composable(NaviRoute.Route) {
                    FrontendRouteResultScreen(
                        viewModel = routeViewModel,
                        onBack = { navController.popBackStack() },
                        onExplain = { navController.navigate(NaviRoute.Explain) },
                        onStart = { navController.navigate(NaviRoute.Navigation) },
                    )
                }
                composable(NaviRoute.GraphCandidates) {
                    val graphCandidateViewModel: GraphCandidateViewModel = viewModel(
                        key = "navi-graph-candidates",
                        factory = NaviViewModelFactory {
                            GraphCandidateViewModel(
                                repository = container.repository,
                                sessionStore = container.sessionStore,
                            )
                        },
                    )
                    GraphCandidateScreen(
                        viewModel = graphCandidateViewModel,
                        onBack = { navController.popBackStack() },
                    )
                }
                composable(NaviRoute.Explain) {
                    FrontendExplainScreen(
                        viewModel = routeViewModel,
                        onBack = { navController.popBackStack() },
                        onReport = { navController.navigate(NaviRoute.ReportForm) },
                        onStart = { navController.navigate(NaviRoute.Navigation) },
                    )
                }
                composable(NaviRoute.Navigation) {
                    FrontendMapNavigationScreen(
                        viewModel = navigationViewModel,
                        onBack = { navController.popBackStack() },
                        onCamera = { navController.navigate(NaviRoute.Camera) },
                        onReport = { navController.navigate(NaviRoute.ReportForm) },
                        onStop = ::stopGuidance,
                    )
                }
                composable(NaviRoute.Camera) {
                    FrontendCameraScreen(
                        viewModel = navigationViewModel,
                        onMap = { navController.popBackStack(NaviRoute.Navigation, false) },
                        onReport = { navController.navigate(NaviRoute.ReportForm) },
                        onStop = ::stopGuidance,
                    )
                }
                composable(NaviRoute.ReportForm) {
                    FrontendReportScreen(
                        viewModel = navigationViewModel,
                        onBack = { navController.popBackStack() },
                        onShowReroute = {
                            navController.navigate(NaviRoute.Reroute) {
                                launchSingleTop = true
                            }
                        },
                    )
                }
                composable(NaviRoute.Reroute) {
                    FrontendRerouteScreen(
                        session = session,
                        onKeep = { navController.popBackStack(NaviRoute.Navigation, false) },
                        onContinue = {
                            navController.navigate(NaviRoute.Navigation) {
                                popUpTo(NaviRoute.Navigation) { inclusive = true }
                            }
                        },
                    )
                }
                composable(NaviRoute.Arrival) {
                    FrontendArrivalScreen(
                        onHome = {
                            container.sessionStore.clearJourney()
                            navController.navigate(NaviRoute.Home) {
                                popUpTo(NaviRoute.Home) { inclusive = true }
                            }
                        },
                        onSave = { navController.navigate(NaviRoute.Saved) },
                    )
                }
            }
        }
        if (showBottomBar) {
            NaviBottomBar(selected = currentRoute, onSelect = { route -> selectTab(route) })
        }
    }
}
