// Interface language. The first visit follows the browser's language and region; a
// choice made in Hesap is remembered. Numbers and dates follow the same locale.

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { setFormatLocale } from "../../format.js";
import de from "./de.js";
import en from "./en.js";
import es from "./es.js";
import fr from "./fr.js";
import tr from "./tr.js";

export const LANGUAGES = [
  { code: "tr", label: "Türkçe", locale: "tr-TR" },
  { code: "en", label: "English", locale: "en-GB" },
  { code: "de", label: "Deutsch", locale: "de-DE" },
  { code: "fr", label: "Français", locale: "fr-FR" },
  { code: "es", label: "Español", locale: "es-ES" },
];

const DICTIONARIES = { tr, en, de, fr, es };
const KEY = "fadir.lang";

function browserLanguages() {
  if (typeof navigator === "undefined") return [];
  return navigator.languages?.length ? navigator.languages : [navigator.language].filter(Boolean);
}

/** The stored choice, else the first browser language faðir speaks, else English. */
function detect() {
  try {
    const stored = localStorage.getItem(KEY);
    if (DICTIONARIES[stored]) return stored;
  } catch { /* private mode */ }
  for (const tag of browserLanguages()) {
    const code = tag.toLowerCase().split("-")[0];
    if (DICTIONARIES[code]) return code;
  }
  return "en";
}

/** Keep the browser's own region for formatting when it speaks the same language (en-US). */
function localeFor(code) {
  const own = browserLanguages().find((tag) => tag.toLowerCase().split("-")[0] === code && tag.includes("-"));
  return own ?? LANGUAGES.find((l) => l.code === code).locale;
}

/** The browser's region, for a sensible default Tax Jurisdiction. */
export function browserRegion() {
  for (const tag of browserLanguages()) {
    const region = tag.split("-")[1];
    if (region && /^[A-Za-z]{2}$/.test(region)) return region.toUpperCase();
  }
  return null;
}

function translate(code, key, vars) {
  const text = DICTIONARIES[code]?.[key] ?? en[key] ?? tr[key] ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name) => (vars[name] ?? match));
}

const I18n = createContext(null);

function apply(code) {
  setFormatLocale(localeFor(code));
  document.documentElement.lang = code;
}

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    const code = detect();
    apply(code);
    return code;
  });

  const setLang = useCallback((code) => {
    if (!DICTIONARIES[code]) return;
    try { localStorage.setItem(KEY, code); } catch { /* private mode */ }
    apply(code);
    setLangState(code);
  }, []);

  const value = useMemo(() => ({
    lang,
    setLang,
    t: (key, vars) => translate(lang, key, vars),
  }), [lang, setLang]);

  return <I18n.Provider value={value}>{children}</I18n.Provider>;
}

export function useI18n() {
  return useContext(I18n);
}

/** `t("key", { name: "value" })`; falls back to English, then Turkish, then the key. */
export function useT() {
  return useContext(I18n).t;
}
