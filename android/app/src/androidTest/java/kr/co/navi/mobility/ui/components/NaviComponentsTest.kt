package kr.co.navi.mobility.ui.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import kr.co.navi.mobility.ui.theme.NaviTheme
import org.junit.Rule
import org.junit.Test

class NaviComponentsTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun primaryActionExposesItsVisibleLabel() {
        composeRule.setContent {
            NaviTheme {
                PrimaryActionButton("접근 가능한 길 찾기", onClick = {})
            }
        }

        composeRule.onNodeWithText("접근 가능한 길 찾기").assertIsDisplayed()
    }
}
