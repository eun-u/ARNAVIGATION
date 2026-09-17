pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "navi-mobility"
include(":app")
include(":core:guidance-contract")
include(":feature:ar-navigation")
include(":feature:ai-perception")
include(":feature:guidance-fusion")
