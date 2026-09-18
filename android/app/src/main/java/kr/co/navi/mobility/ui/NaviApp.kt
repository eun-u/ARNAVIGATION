package kr.co.navi.mobility.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
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
import kr.co.navi.mobility.ui.screens.ArrivalScreen
import kr.co.navi.mobility.ui.screens.CameraScreen
import kr.co.navi.mobility.ui.screens.ExplainScreen
import kr.co.navi.mobility.ui.screens.GraphCandidateScreen
import kr.co.navi.mobility.ui.screens.HomeScreen
import kr.co.navi.mobility.ui.screens.NavigationScreen
import kr.co.navi.mobility.ui.screens.PlanScreen
import kr.co.navi.mobility.ui.screens.ProfileScreen
import kr.co.navi.mobility.ui.screens.ReportHubScreen
import kr.co.navi.mobility.ui.screens.ReportScreen
import kr.co.navi.mobility.ui.screens.RouteScreen

/**
 * 상시 목적지 4개(홈 · 길찾기 · 제보 · 내 정보) 위에
 * 안내 흐름이 전체화면으로 덮이는 구조.
 *
 * 탭 전환은 각 탭의 백스택을 보존하고, 안내(경로 결과 · 지도 · AR · 제보 작성 · 도착)는
 * 탭바를 가린다. 자세한 규칙은 docs/screen_state_matrix.md 참고.
 */
private object NaviRoute {
    const val Home = "home"
    const val Plan = "plan"
    const val ReportHub = "report"
    const val Profile = "profile"

    const val Route = "route"
    const val Explain = "explain"
    const val GraphCandidates = "graph-candidates"
    const val Navigation = "navigation"
    const val Camera = "camera"
    const val ReportForm = "report-form"
    const val Arrival = "arrival"
}

@Composable
fun NaviApp(container: NaviAppContainer) {
    val navController = rememberNavController()
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
    val currentRoute = backStackEntry?.destination?.route ?: NaviRoute.Home
    val tabRoutes = NaviDestinations.map { it.route }
    val showBottomBar = currentRoute in tabRoutes

    fun selectTab(route: String) {
        navController.navigate(route) {
            popUpTo(NaviRoute.Home) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    Column(Modifier.fillMaxSize()) {
        Box(Modifier.weight(1f)) {
            NavHost(
                navController = navController,
                startDestination = NaviRoute.Home,
            ) {
                // ── 상시 목적지 ────────────────────────────────────────────
                composable(NaviRoute.Home) {
                    HomeScreen(
                        session = session,
                        onFindRoute = { selectTab(NaviRoute.Plan) },
                        onResumeGuidance = { navController.navigate(NaviRoute.Navigation) },
                        onEditProfile = { selectTab(NaviRoute.Plan) },
                    )
                }
                composable(NaviRoute.Plan) {
                    PlanScreen(
                        viewModel = planViewModel,
                        onRouteReady = { navController.navigate(NaviRoute.Route) },
                    )
                }
                composable(NaviRoute.ReportHub) {
                    ReportHubScreen(
                        session = session,
                        onWriteReport = { navController.navigate(NaviRoute.ReportForm) },
                    )
                }
                composable(NaviRoute.Profile) {
                    ProfileScreen(
                        session = session,
                        onEditProfile = { selectTab(NaviRoute.Plan) },
                    )
                }

                // ── 안내 흐름 · 탭바를 덮는다 ──────────────────────────────
                composable(NaviRoute.Route) {
                    RouteScreen(
                        viewModel = routeViewModel,
                        onBack = { navController.popBackStack() },
                        onExplain = { navController.navigate(NaviRoute.Explain) },
                        onCandidates = { navController.navigate(NaviRoute.GraphCandidates) },
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
                    ExplainScreen(
                        viewModel = routeViewModel,
                        onBack = { navController.popBackStack() },
                    )
                }
                composable(NaviRoute.Navigation) {
                    NavigationScreen(
                        viewModel = navigationViewModel,
                        onBack = { navController.popBackStack() },
                        onCamera = { navController.navigate(NaviRoute.Camera) },
                        onReport = { navController.navigate(NaviRoute.ReportForm) },
                        onFinish = { navController.navigate(NaviRoute.Arrival) },
                    )
                }
                composable(NaviRoute.Camera) {
                    CameraScreen(
                        viewModel = navigationViewModel,
                        onBack = { navController.popBackStack() },
                        onMap = { navController.popBackStack(NaviRoute.Navigation, false) },
                        onReport = { navController.navigate(NaviRoute.ReportForm) },
                    )
                }
                composable(NaviRoute.ReportForm) {
                    ReportScreen(
                        viewModel = navigationViewModel,
                        onBack = { navController.popBackStack() },
                        onShowReroute = {
                            navController.popBackStack(NaviRoute.Navigation, false)
                        },
                    )
                }
                composable(NaviRoute.Arrival) {
                    ArrivalScreen(
                        viewModel = routeViewModel,
                        onNewRoute = {
                            container.sessionStore.clearJourney()
                            navController.navigate(NaviRoute.Home) {
                                popUpTo(NaviRoute.Home) { inclusive = true }
                            }
                        },
                    )
                }
            }
        }
        if (showBottomBar) {
            NaviBottomBar(selected = currentRoute, onSelect = { route -> selectTab(route) })
        }
    }
}
