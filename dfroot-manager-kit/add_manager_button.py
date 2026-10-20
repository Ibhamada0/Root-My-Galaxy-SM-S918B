#!/usr/bin/env python3
"""Add a user-initiated official manager download button to the Android UI."""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
def edit(path, old, new):
    f = root / path
    text = f.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"Unexpected upstream source at {path}")
    f.write_text(text.replace(old, new, 1), encoding="utf-8")

edit("app/src/main/res/layout/activity_main.xml",
     '                android:text="Auto Soft Reboot" />\n\n        </LinearLayout>\n\n    </com.google.android.material.card.MaterialCardView>\n\n    <ScrollView',
     '                android:text="Auto Soft Reboot" />\n\n            <Button\n                android:id="@+id/btnManager"\n                android:layout_width="match_parent"\n                android:layout_height="wrap_content"\n                android:layout_marginTop="8dp"\n                android:text="Install KernelSU Next Manager" />\n\n        </LinearLayout>\n\n    </com.google.android.material.card.MaterialCardView>\n\n    <ScrollView')

edit("app/src/main/java/df/root/MainActivity.java",
     "import android.os.Bundle;",
     "import android.os.Bundle;\nimport android.content.Intent;\nimport android.net.Uri;")

edit("app/src/main/java/df/root/MainActivity.java",
     "        setSupportActionBar(binding.toolbar);",
     """        setSupportActionBar(binding.toolbar);
        binding.btnManager.setOnClickListener(v -> {
            Uri uri = Uri.parse("https://github.com/KernelSU-Next/KernelSU-Next/releases/download/v3.4.2/KernelSU_Next_v3.4.2_33355-release.apk");
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        });""")

edit("app/src/main/java/df/root/MainActivity.java",
     '    private static final String TAG = "dfroot";',
     '    private static final String TAG = "dfroot";')

edit("gradle/wrapper/gradle-wrapper.properties",
     "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.7.1-bin.zip",
     "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.9-bin.zip")
print("Manager button added; all other app code unchanged.")
