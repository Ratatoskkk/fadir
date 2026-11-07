// Google Identity Services loader, shared by both interfaces.
//
// Production loads the real GIS script. Development builds never reach Google: with
// `?synthetic-google` in the URL they get a synthetic provider for local testing.

const GIS_SCRIPT_ID = "google-gsi-client";
const GIS_SCRIPT_SRC = "https://accounts.google.com/gsi/client";
let syntheticGoogleConfig = null;

function syntheticGoogleServices() {
  return {
    accounts: {
      id: {
        initialize(config) {
          syntheticGoogleConfig = config;
        },
        renderButton(node) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "btn primary";
          button.textContent = "Sentetik Google";
          button.addEventListener("click", () => {
            syntheticGoogleConfig?.callback({ credential: "synthetic-proof-credential" });
          });
          node.replaceChildren(button);
        },
      },
    },
  };
}

export function loadGoogleIdentityServices() {
  if (typeof window !== "undefined" && window.google?.accounts?.id) {
    return Promise.resolve(window.google);
  }
  if (!import.meta.env.PROD) {
    if (new URLSearchParams(window.location.search).has("synthetic-google")) {
      return Promise.resolve(syntheticGoogleServices());
    }
    return Promise.reject(new Error("Sentetik Google sağlayıcısı hazır değil."));
  }
  return new Promise((resolve, reject) => {
    const existing = document.getElementById(GIS_SCRIPT_ID);
    if (existing) {
      existing.addEventListener("load", () => resolve(window.google), { once: true });
      existing.addEventListener("error", () => reject(new Error("Google sağlayıcısı yüklenemedi.")), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.id = GIS_SCRIPT_ID;
    script.src = GIS_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve(window.google);
    script.onerror = () => reject(new Error("Google sağlayıcısı yüklenemedi."));
    document.head.appendChild(script);
  });
}
