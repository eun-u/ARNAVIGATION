package kr.co.navi.mobility.data.remote

import kr.co.navi.mobility.data.model.ObservationCandidateCreateDto
import kr.co.navi.mobility.data.model.SessionRerouteRequestDto
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NaviApiClientTest {
    @Test
    fun `manual observation remains pending and unverified`() = runTest {
        var captured: HttpRequest? = null
        val transport = HttpTransport { request ->
            captured = request
            HttpResponse(
                201,
                """{
                    "candidate_id":"MOB_1",
                    "edge_id":"E15",
                    "type":"construction",
                    "source":"manual_camera",
                    "confidence":null,
                    "status":"pending",
                    "verified":false,
                    "session_id":"S01"
                }""".trimIndent(),
            )
        }
        val client = NaviApiClient("http://127.0.0.1:8000", transport)

        val result = client.createCandidate(
            ObservationCandidateCreateDto(
                edgeId = "E15",
                type = "construction",
                source = "manual_camera",
                sessionId = "S01",
            ),
        )

        assertEquals("pending", result.status)
        assertFalse(result.verified)
        assertNull(result.confidence)
        assertEquals(HttpMethod.POST, captured?.method)
        assertEquals("http://127.0.0.1:8000/observations/candidates", captured?.url)
        assertTrue(captured?.body.orEmpty().contains("\"edge_id\":\"E15\""))
    }

    @Test
    fun `session id is URL encoded for reroute`() = runTest {
        var capturedUrl = ""
        val transport = HttpTransport { request ->
            capturedUrl = request.url
            HttpResponse(
                200,
                """{
                    "status":"rerouted",
                    "session_id":"session / 1",
                    "temporary_blocked_edge_ids":["E15"],
                    "graph_revision":1,
                    "route_affected":true,
                    "route_changed":true
                }""".trimIndent(),
            )
        }
        val client = NaviApiClient("http://127.0.0.1:8000/", transport)

        client.reroute(
            "session / 1",
            SessionRerouteRequestDto(listOf("E15"), "construction"),
        )

        assertTrue(capturedUrl.endsWith("/route/sessions/session%20%2F%201/reroute"))
    }

    @Test
    fun `structured backend error is exposed`() = runTest {
        val client = NaviApiClient(
            "http://127.0.0.1:8000",
            HttpTransport {
                HttpResponse(
                    404,
                    """{"detail":{"code":"session_not_found","message":"세션이 만료되었습니다."}}""",
                )
            },
        )

        val error = runCatching {
            client.reroute("missing", SessionRerouteRequestDto(listOf("E15"), "blocked_path"))
        }.exceptionOrNull() as NaviApiException

        assertEquals(404, error.statusCode)
        assertEquals("session_not_found", error.errorCode)
        assertEquals("세션이 만료되었습니다.", error.message)
    }
}
