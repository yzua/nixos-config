package org.pi.re.fixture;

import android.app.Activity;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.InputStream;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;

/** Owned UI/runtime/HTTPS fixture; no accounts or custom TLS trust overrides. */
public final class MainActivity extends Activity {
    private int count = 0;

    public int increment() { return ++count; }

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(36, 72, 36, 36);
        TextView counter = new TextView(this);
        counter.setText("Counter: 0");
        Button button = new Button(this);
        button.setText("Increment");
        button.setContentDescription("Increment fixture counter");
        button.setOnClickListener(view -> counter.setText("Counter: " + increment()));
        layout.addView(counter);
        layout.addView(button);
        TextView https = new TextView(this);
        https.setText("HTTPS: idle");
        Button fetch = new Button(this);
        fetch.setText("Fetch HTTPS fixture");
        fetch.setContentDescription("Fetch HTTPS fixture");
        fetch.setOnClickListener(view -> new Thread(() -> {
            HttpsURLConnection connection = null;
            try {
                String target = getIntent().getStringExtra("fixture_url");
                if (target == null || !target.startsWith("https://pi-re.fixture.test/")) {
                    throw new IllegalArgumentException("Missing owned fixture URL");
                }
                connection = (HttpsURLConnection) new URL(target).openConnection();
                connection.setConnectTimeout(5000);
                connection.setReadTimeout(5000);
                InputStream stream = connection.getInputStream();
                byte[] buffer = new byte[4096];
                int count = stream.read(buffer);
                stream.close();
                String proof = new String(buffer, 0, count, "UTF-8");
                runOnUiThread(() -> https.setText("HTTPS: " + proof));
            } catch (Exception error) {
                runOnUiThread(() -> https.setText("HTTPS: error:" + error.getClass().getSimpleName()));
            } finally {
                if (connection != null) connection.disconnect();
            }
        }).start());
        layout.addView(https);
        layout.addView(fetch);
        setContentView(layout);
    }
}
