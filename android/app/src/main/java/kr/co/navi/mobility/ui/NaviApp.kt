package kr.co.navi.mobility.ui

import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import kr.co.navi.mobility.NaviAppContainer
import kr.co.navi.mobility.ui.screens.ArrivalScreen
import kr.co.navi.mobility.ui.screens.CameraScreen
import kr.co.navi.mobility.ui.screens.ExplainScreen
import kr.co.navi.mobility.ui.screens.NavigationScreen
import kr.co.navi.mobility.ui.screens.PlanScreen
import kr.co.navi.mobility.ui.screens.ReportScreen
import kr.co.navi.mobility.ui.screens.RouteScreen

private object NaviDestination {
    const val Plan = "plan"
    const val Route = "route"
    const val Explain = "explain"
    const val Navigation = "navigation"
    const val Camera = "camera"
    const val Report = "report"
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

    NavHost(
        navController = navController,
        startDestination = NaviDestination.Plan,
    ) {
        composable(NaviDestination.Plan) {
            PlanScreen(
                viewModel = planViewModel,
                onRouteReady = { navController.navigate(NaviDestination.Route) },
            )
        }
        composable(NaviDestination.Route) {
            RouteScreen(
                viewModel = routeViewModel,
                onBack = { navController.popBackStack() },
                onExplain = { navController.navigate(NaviDestination.Explain) },
                onStart = { navController.navigate(NaviDestination.Navigation) },
            )
        }
        composable(NaviDestination.Explain) {
            ExplainScreen(
                viewModel = routeViewModel,
                onBack = { navController.popBackStack() },
            )
        }
        composable(NaviDestination.Navigation) {
            NavigationScreen(
                viewModel = navigationViewModel,
                onBack = { navController.popBackStack() },
                onCamera = { navController.navigate(NaviDestination.Camera) },
                onReport = { navController.navigate(NaviDestination.Report) },
                onFinish = { navController.navigate(NaviDestination.Arrival) },
            )
        }
        composable(NaviDestination.Camera) {
            CameraScreen(
                viewModel = navigationViewModel,
                onBack = { navController.popBackStack() },
                onMap = { navController.popBackStack(NaviDestination.Navigation, false) },
                onReport = { navController.navigate(NaviDestination.Report) },
            )
        }
        composable(NaviDestination.Report) {
            ReportScreen(
                viewModel = navigationViewModel,
                onBack = { navController.popBackStack() },
                onShowReroute = {
                    navController.popBackStack(NaviDestination.Navigation, false)
                },
            )
        }
        composable(NaviDestination.Arrival) {
            ArrivalScreen(
                viewModel = routeViewModel,
                onNewRoute = {
                    container.sessionStore.clearJourney()
                    navController.navigate(NaviDestination.Plan) {
                        popUpTo(NaviDestination.Plan) { inclusive = true }
                    }
                },
            )
        }
    }
}
