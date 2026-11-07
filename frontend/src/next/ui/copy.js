/** Copy a Portfolio Code and say so. */
export async function copyCode(code, toast, t) {
  try {
    await navigator.clipboard.writeText(code);
    toast({ tone: "up", text: t("code.copied") });
  } catch {
    toast({ tone: "down", text: t("code.copyFailed") });
  }
}
