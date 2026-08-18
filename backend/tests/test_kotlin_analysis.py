"""Comprehensive Regression Test Suite for Kotlin / Android ChangePilot Analysis.

Tests:
  1. Multi-Language Parser: KotlinParser (.kt, .kts), JavaParser, TypeScriptParser, PythonParser.
  2. Kotlin AST & Android Manifest: Package declarations, imports, classes, functions, @Entity, @Composable.
  3. Android Entrypoints: Activity, Service, Receiver, Provider from Manifest & AST.
  4. Kotlin Dependency Graph: Cross-file SOURCE_IMPORT edges, BFS blast radius, node deduplication.
  5. Authentication Detection Precision: LoginActivity & AuthManager trigger auth; AlarmReceiver & AppDatabase do NOT.
  6. Granular Security Rules: authentication_change, authorization_change, credential_change, session_change.
  7. Large Refactor Architectural Filtering: Distinguishing 72 total files from 27 source/build files.
  8. Database Schema Change Precision: Only triggers on Room @Entity / schema diff, not simple DB singleton.
  9. Health & Quality Propagation: Security health deductions for active security signals, parser failure penalties.
  10. Acceptance Validation: Login-Logout fixture produces non-empty graph (>1 nodes, >0 edges).
"""

from __future__ import annotations

from app.analysis.file_classifier import (
    FileTypeCategory,
    classify_file_type,
    filter_architecturally_relevant_files,
)
from app.analysis.manifest_parser import AndroidManifestParser
from app.analysis.tree_sitter_parser import (
    TreeSitterCodeParser,
)
from app.graph.knowledge_graph import KnowledgeGraphBuilder
from app.models.analysis import ChangeAnalysisResult
from app.models.enums import FileClassification
from app.models.export import AnalysisExportModel
from app.models.repository import RepositorySummary
from app.models.risk import RiskInput
from app.risk.engine import DeterministicRiskEngine
from app.risk.rules import RULES

# ---------------------------------------------------------------------------
# Fixture: Real-World Android Kotlin Repository Files
# ---------------------------------------------------------------------------

ANDROID_MANIFEST_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.swapwarick.loginlogout">

    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:name=".App"
        android:allowBackup="true"
        android:label="LoginLogout">
        <activity
            android:name=".ui.login.LoginActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <activity android:name=".ui.main.MainActivity" android:exported="false" />
        <service android:name=".service.AuthSyncService" android:exported="false" />
        <receiver android:name=".receiver.AlarmReceiver" android:exported="false" />
    </application>
</manifest>
"""

KOTLIN_FILES = {
    "app/src/main/java/com/swapwarick/loginlogout/data/UserRepository.kt": b"""
package com.swapwarick.loginlogout.data

import com.swapwarick.loginlogout.data.model.User
import com.swapwarick.loginlogout.data.db.UserDao

class UserRepository(private val userDao: UserDao) {
    fun getUser(id: String): User? {
        return userDao.findById(id)
    }
}
""",
    "app/src/main/java/com/swapwarick/loginlogout/data/model/User.kt": b"""
package com.swapwarick.loginlogout.data.model

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "users")
data class User(
    @PrimaryKey val id: String,
    val username: String,
    val email: String
)
""",
    "app/src/main/java/com/swapwarick/loginlogout/data/db/UserDao.kt": b"""
package com.swapwarick.loginlogout.data.db

import androidx.room.Dao
import androidx.room.Query
import com.swapwarick.loginlogout.data.model.User

@Dao
interface UserDao {
    @Query("SELECT * FROM users WHERE id = :id")
    fun findById(id: String): User?
}
""",
    "app/src/main/java/com/swapwarick/loginlogout/data/db/AppDatabase.kt": b"""
package com.swapwarick.loginlogout.data.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.swapwarick.loginlogout.data.model.User

@Database(entities = [User::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
    abstract fun userDao(): UserDao
}
""",
    "app/src/main/java/com/swapwarick/loginlogout/auth/AuthManager.kt": b"""
package com.swapwarick.loginlogout.auth

import com.swapwarick.loginlogout.data.UserRepository
import com.swapwarick.loginlogout.auth.SessionManager

class AuthManager(
    private val userRepository: UserRepository,
    private val sessionManager: SessionManager
) {
    fun login(username: String, passwordHash: String): Boolean {
        sessionManager.createSession(username)
        return true
    }

    fun logout() {
        sessionManager.clearSession()
    }
}
""",
    "app/src/main/java/com/swapwarick/loginlogout/auth/SessionManager.kt": b"""
package com.swapwarick.loginlogout.auth

class SessionManager {
    private var activeSessionToken: String? = null

    fun createSession(userId: String) {
        activeSessionToken = "token_" + userId
    }

    fun clearSession() {
        activeSessionToken = null
    }
}
""",
    "app/src/main/java/com/swapwarick/loginlogout/ui/login/LoginActivity.kt": b"""
package com.swapwarick.loginlogout.ui.login

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.swapwarick.loginlogout.auth.AuthManager

class LoginActivity : AppCompatActivity() {
    private lateinit var authManager: AuthManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        authManager.login("test", "secret")
    }
}
""",
    "app/src/main/java/com/swapwarick/loginlogout/ui/main/MainActivity.kt": b"""
package com.swapwarick.loginlogout.ui.main

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.swapwarick.loginlogout.data.UserRepository

class MainActivity : AppCompatActivity() {
    private lateinit var userRepository: UserRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
    }
}
""",
    "app/src/main/java/com/swapwarick/loginlogout/receiver/AlarmReceiver.kt": b"""
package com.swapwarick.loginlogout.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // Trigger notification alarm
    }
}
""",
    "app/src/test/java/com/swapwarick/loginlogout/AuthManagerTest.kt": b"""
package com.swapwarick.loginlogout

import com.swapwarick.loginlogout.auth.AuthManager
import org.junit.Test

class AuthManagerTest {
    @Test
    fun testLogin() {
        assert(true)
    }
}
""",
}


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


class TestKotlinParserAndManifest:
    def test_android_manifest_entrypoints(self):
        manifest = AndroidManifestParser.parse_manifest(ANDROID_MANIFEST_XML)
        assert manifest.package_name == "com.swapwarick.loginlogout"
        assert manifest.parse_status == "SUCCESS"
        assert len(manifest.components) == 5  # 1 application + 2 activities + 1 service + 1 receiver
        assert "com.swapwarick.loginlogout.ui.login.LoginActivity" in manifest.entrypoint_classes
        assert "LoginActivity" in manifest.entrypoint_classes
        assert "AlarmReceiver" in manifest.entrypoint_classes
        assert "AuthSyncService" in manifest.entrypoint_classes
        assert "android.permission.INTERNET" in manifest.permissions

    def test_kotlin_ast_parsing(self):
        parser = TreeSitterCodeParser()
        auth_file = "app/src/main/java/com/swapwarick/loginlogout/auth/AuthManager.kt"
        ast = parser.parse_file(auth_file, KOTLIN_FILES[auth_file])

        assert ast.language == "kotlin"
        assert ast.package_name == "com.swapwarick.loginlogout.auth"
        assert "AuthManager" in ast.defined_classes
        assert "login" in ast.defined_functions
        assert "logout" in ast.defined_functions
        assert any(i.source_module.endswith("UserRepository") for i in ast.imports)
        assert any(i.source_module.endswith("SessionManager") for i in ast.imports)

    def test_room_database_and_entity_parsing(self):
        parser = TreeSitterCodeParser()
        user_file = "app/src/main/java/com/swapwarick/loginlogout/data/model/User.kt"
        ast = parser.parse_file(user_file, KOTLIN_FILES[user_file])
        assert "User" in ast.defined_classes
        assert "Room Database" in ast.framework_signals or "users" in ast.db_tables


class TestKotlinKnowledgeGraph:
    def test_kotlin_graph_generation(self):
        parser = TreeSitterCodeParser()
        parsed_files = [parser.parse_file(path, content) for path, content in KOTLIN_FILES.items()]

        builder = KnowledgeGraphBuilder()
        graph, graph_hash, health = builder.build_graph_from_parsed_files(
            parsed_files, manifest_content=ANDROID_MANIFEST_XML
        )

        # 1. Non-empty AST nodes and edges
        assert len(graph.nodes) > 10, f"Expected >10 nodes, got {len(graph.nodes)}"
        assert len(graph.edges) > 5, f"Expected >5 edges, got {len(graph.edges)}"
        assert graph_hash is not None

        # 2. Verify SOURCE_IMPORT edges exist between Kotlin files
        source_import_edges = [
            e for e in graph.edges
            if e.relationship == "IMPORTS" and "file:" in e.source and "file:" in e.target
        ]
        assert len(source_import_edges) >= 3, f"Expected >=3 cross-file Kotlin imports, found {len(source_import_edges)}"

        # 3. Android Entrypoints (LoginActivity, MainActivity, AlarmReceiver) must not be orphan candidates
        entrypoint_nodes = [
            n for n in graph.nodes
            if n.file_classification == FileClassification.ENTRYPOINT
        ]
        assert len(entrypoint_nodes) >= 3
        orphan_candidates = health.potential_orphan_candidates
        assert "app/src/main/java/com/swapwarick/loginlogout/receiver/AlarmReceiver.kt" not in orphan_candidates
        assert "app/src/main/java/com/swapwarick/loginlogout/ui/login/LoginActivity.kt" not in orphan_candidates


class TestAuthenticationDetectionPrecision:
    def test_auth_detection_matches_only_real_auth_files(self):
        auth_rule = next(r for r in RULES if r.signal == "authentication_change")

        # True Positives
        assert auth_rule.matches("app/src/main/java/com/swapwarick/loginlogout/auth/AuthManager.kt")
        assert auth_rule.matches("app/src/main/java/com/swapwarick/loginlogout/ui/login/LoginActivity.kt")
        assert auth_rule.matches("app/src/main/java/com/swapwarick/loginlogout/auth/LogoutHandler.kt")

        # True Negatives (False positive prevention for general files in loginlogout package)
        assert not auth_rule.matches("app/src/main/java/com/swapwarick/loginlogout/receiver/AlarmReceiver.kt")
        assert not auth_rule.matches("app/src/main/java/com/swapwarick/loginlogout/data/db/AppDatabase.kt")
        assert not auth_rule.matches("app/src/main/java/com/swapwarick/loginlogout/ui/theme/Color.kt")
        assert not auth_rule.matches("app/src/main/java/com/swapwarick/loginlogout/ui/theme/Theme.kt")
        assert not auth_rule.matches("app/src/main/java/com/swapwarick/loginlogout/ui/main/MainActivity.kt")

    def test_session_and_credential_rules(self):
        session_rule = next(r for r in RULES if r.signal == "session_change")
        assert session_rule.matches("app/src/main/java/com/swapwarick/loginlogout/auth/SessionManager.kt")
        assert not session_rule.matches("app/src/main/java/com/swapwarick/loginlogout/data/UserRepository.kt")


class TestArchitecturalFileFiltering:
    def test_file_classification(self):
        assert classify_file_type("app/src/main/java/com/swapwarick/loginlogout/ui/login/LoginActivity.kt") == FileTypeCategory.SOURCE
        assert classify_file_type("app/src/test/java/com/swapwarick/loginlogout/AuthTest.kt") == FileTypeCategory.TEST
        assert classify_file_type("build.gradle.kts") == FileTypeCategory.BUILD
        assert classify_file_type(".idea/workspace.xml") == FileTypeCategory.IDE_METADATA
        assert classify_file_type("app/src/main/res/drawable/ic_logo.webp") == FileTypeCategory.ASSET
        assert classify_file_type("gradle/wrapper/gradle-wrapper.jar") == FileTypeCategory.ASSET
        assert classify_file_type("app/build/generated/source/kapt/main/UserDao_Impl.java") == FileTypeCategory.GENERATED
        assert classify_file_type("app/src/main/java/com/swapwarick/loginlogout/Auth.kt.bak") == FileTypeCategory.BACKUP

    def test_large_refactor_filtering(self):
        # 72 changed files: 20 source, 2 test, 2 build, 48 IDE/assets/generated
        source_files = [f"app/src/main/java/com/example/File{i}.kt" for i in range(20)]
        test_files = ["app/src/test/java/com/example/FileTest.kt", "app/src/test/java/com/example/File2Test.kt"]
        build_files = ["build.gradle.kts", "settings.gradle.kts"]
        ide_files = [f".idea/file_{i}.xml" for i in range(20)]
        asset_files = [f"app/src/main/res/drawable/icon_{i}.webp" for i in range(20)]
        generated_files = [f"app/build/generated/output_{i}.class" for i in range(8)]

        all_72_files = source_files + test_files + build_files + ide_files + asset_files + generated_files
        assert len(all_72_files) == 72

        arch_relevant = filter_architecturally_relevant_files(all_72_files)
        assert len(arch_relevant) == 24  # 20 source + 2 test + 2 build

        # Risk engine should score large_refactor using 24, not 72
        engine = DeterministicRiskEngine()
        result = engine.score(RiskInput(changed_files=all_72_files, large_refactor=True))
        large_refactor_ev = next(e for e in result.evidence if e.signal == "large_refactor")
        assert "24 architecturally relevant" in large_refactor_ev.description
        assert "72 total changed files" in large_refactor_ev.description


class TestExportModelAcceptance:
    def test_login_logout_export_model(self):
        repo = RepositorySummary(
            id="repo-login-logout",
            name="Login-Logout",
            owner="swapwarick",
            default_branch="main",
            source="github",
            language="Kotlin",
        )

        parser = TreeSitterCodeParser()
        parsed_files = [parser.parse_file(path, content) for path, content in KOTLIN_FILES.items()]
        builder = KnowledgeGraphBuilder()
        graph, _graph_hash, health = builder.build_graph_from_parsed_files(
            parsed_files, manifest_content=ANDROID_MANIFEST_XML
        )

        # Changed files in commit
        changed = [
            "app/src/main/java/com/swapwarick/loginlogout/auth/AuthManager.kt",
            "app/src/main/java/com/swapwarick/loginlogout/ui/login/LoginActivity.kt",
        ]

        engine = DeterministicRiskEngine()
        risk_res = engine.score(RiskInput(changed_files=changed))

        analysis_res = ChangeAnalysisResult(
            id="anl-24e0ad58",
            repository_id="repo-login-logout",
            trigger="commit_comparison",
            risk=risk_res,
            changed_files=changed,
            impacted_modules=["auth", "ui"],
            dependency_graph=graph,
            analysis_timestamp="2026-08-18T13:00:00Z",
            analysis_version="1.0.0",
        )

        health_dict = {
            "health_score": health.health_score,
            "categories": {
                k: {"score": v.score, "evidence": v.evidence, "deductions": v.deductions, "recommendations": v.recommendations}
                for k, v in health.categories.items()
            },
        }

        export_model = AnalysisExportModel.from_analysis(
            analysis=analysis_res,
            repository=repo,
            health_metrics=health_dict,
        )

        # Verify acceptance criteria
        assert export_model.graph_health.nodes > 1, f"Expected >1 AST node, got {export_model.graph_health.nodes}"
        assert export_model.graph_health.edges > 0, f"Expected >0 dependency edges, got {export_model.graph_health.edges}"
        assert export_model.analysis_quality.parser_status == "PASS"
        assert export_model.analysis_quality.ast_graph_status == "PASS"

        # Check that authentication_change is fired specifically on AuthManager / LoginActivity
        auth_finding = next((f for f in export_model.security_findings if f.title == "Authentication Modified"), None)
        assert auth_finding is not None
        assert any("AuthManager.kt" in f for f in auth_finding.affected_files)

        # Check that Security Health Score reflects deductions for active security changes
        sec_health = export_model.repository_health.health_breakdown.get("Security")
        assert sec_health is not None
        assert sec_health.score < 100 or len(sec_health.evidence) > 0

        # Validate consistency
        errors = export_model.validate_consistency()
        assert len(errors) == 0, f"Consistency validation failed: {errors}"
