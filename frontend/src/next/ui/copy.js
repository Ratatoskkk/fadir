/** Copy a Portfolio Code and say so. */
export async function copyCode(code, toast) {
  try {
    await navigator.clipboard.writeText(code);
    toast({ tone: "up", text: "Kod kopyalandı" });
  } catch {
    toast({ tone: "down", text: "Kopyalanamadı." });
  }
}
