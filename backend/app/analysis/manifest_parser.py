"""Android Manifest and Build Specification Parser for ChangePilot.

Extracts:
  - Application entrypoints (Activity, Service, BroadcastReceiver, ContentProvider)
  - Application class declarations
  - Permissions and security configurations
  - Package namespaces and component mappings
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


@dataclass
class AndroidComponent:
    kind: str  # activity, service, receiver, provider, application
    name: str  # Fully qualified or relative class name (e.g. .ui.login.LoginActivity)
    exported: bool = False
    permission: str | None = None
    intent_filters: list[str] = field(default_factory=list)


@dataclass
class ParsedAndroidManifest:
    package_name: str = ""
    application_class: str | None = None
    components: list[AndroidComponent] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    entrypoint_classes: set[str] = field(default_factory=set)
    parse_status: str = "SUCCESS"
    parse_errors: list[str] = field(default_factory=list)


class AndroidManifestParser:
    """Parses AndroidManifest.xml to extract entrypoint components and security policies."""

    @staticmethod
    def parse_manifest(content_bytes: bytes, file_path: str = "AndroidManifest.xml") -> ParsedAndroidManifest:
        result = ParsedAndroidManifest()
        try:
            root = ET.fromstring(content_bytes)
            package_name = root.attrib.get("package", "")
            result.package_name = package_name

            # Extract permissions
            for elem in root.findall("uses-permission"):
                name = elem.attrib.get(f"{ANDROID_NS}name", elem.attrib.get("name", ""))
                if name:
                    result.permissions.append(name)

            app_elem = root.find("application")
            if app_elem is not None:
                app_name = app_elem.attrib.get(f"{ANDROID_NS}name", app_elem.attrib.get("name", ""))
                if app_name:
                    resolved_app = AndroidManifestParser._resolve_class_name(package_name, app_name)
                    result.application_class = resolved_app
                    result.entrypoint_classes.add(resolved_app)
                    result.components.append(AndroidComponent(kind="application", name=resolved_app))

                for tag, kind in [
                    ("activity", "activity"),
                    ("service", "service"),
                    ("receiver", "receiver"),
                    ("provider", "provider"),
                    ("activity-alias", "activity"),
                ]:
                    for comp in app_elem.findall(tag):
                        raw_name = comp.attrib.get(f"{ANDROID_NS}name", comp.attrib.get("name", ""))
                        if not raw_name:
                            continue
                        resolved = AndroidManifestParser._resolve_class_name(package_name, raw_name)
                        exported_val = comp.attrib.get(f"{ANDROID_NS}exported", "").lower()
                        exported = exported_val == "true"
                        perm = comp.attrib.get(f"{ANDROID_NS}permission", None)

                        filters: list[str] = []
                        for inf in comp.findall("intent-filter"):
                            for act in inf.findall("action"):
                                act_name = act.attrib.get(f"{ANDROID_NS}name", act.attrib.get("name", ""))
                                if act_name:
                                    filters.append(act_name)

                        result.components.append(
                            AndroidComponent(
                                kind=kind,
                                name=resolved,
                                exported=exported,
                                permission=perm,
                                intent_filters=filters,
                            )
                        )
                        result.entrypoint_classes.add(resolved)
                        # Also add short name (e.g. LoginActivity)
                        short_name = resolved.split(".")[-1]
                        result.entrypoint_classes.add(short_name)

        except Exception as exc:
            logger.warning("Failed to parse AndroidManifest.xml at %s: %s", file_path, exc)
            result.parse_status = "FAILED"
            result.parse_errors.append(str(exc))

        return result

    @staticmethod
    def _resolve_class_name(package_name: str, class_name: str) -> str:
        if class_name.startswith("."):
            return f"{package_name}{class_name}"
        if "." not in class_name and package_name:
            return f"{package_name}.{class_name}"
        return class_name
