/* MedMatch i18n — self-contained, no deps. 6 languages.
 * Usage: const t = (k, fb) => I18N.t(k, fb);
 * Switch: I18N.setLang('vi') → persists + re-applies [data-i18n] + fires 'medmatch:lang'.
 * The FDA statement stays VERBATIM English (US regulation) — a translated
 * supplementary line renders next to it, never instead of it.
 */
"use strict";

(function () {
  const DICTS = {
    en: {
      tab_scan: "Scan", tab_cabinet: "My Cabinet", tab_check: "Check", tab_review: "Review",
      btn_start_camera: "Start camera", btn_lookup: "Look up", btn_ocr: "Scan label text (OCR)",
      btn_search: "Search", btn_check_interactions: "Check for interactions", btn_print: "Print / Save as PDF",
      btn_verify: "✓ Verify", btn_reject: "✗ Reject", btn_add: "Add",
      title_scan_product: "Scan a product", title_manual_add: "Add manually",
      title_cabinet: "My cabinet", title_review_queue: "Review queue",
      title_unmatched: "Could not identify", title_depletions: "Nutrient depletion watch",
      title_cascades: "Hidden risk chains", title_qt: "QT prolongation risk",
      title_elytes: "Electrolyte watch", title_beers: "Beers Criteria (age 65+)",
      title_schedule: "Scheduling suggestions",
      scan_intro: "Point your camera at the barcode, or enter it manually.",
      cabinet_intro: "Your supplements and medications are stored only in this browser.",
      review_intro: "Pharmacist triage for inferred interactions (trust 0.5). Verify or reject.",
      unmatched_intro: "These items were not recognized — check spelling or add them via search:",
      depletions_intro: "These medications may deplete nutrients over time — worth discussing supplementation with your doctor.",
      cascades_intro: "Inferred from enzyme pathways — mechanism-based signal, not a directly documented interaction.",
      qt_intro: "Combining QT-prolonging drugs raises the chance of a dangerous heart rhythm (torsades).",
      elytes_intro: "These medications can drain potassium/magnesium — an occasional blood test is worth it.",
      beers_intro: "AGS Beers 2023 — medications needing extra caution in older adults.",
      schedule_intro: "Absorption conflicts — spacing doses apart defuses these.",
      msg_nothing: "Nothing to check yet", msg_nothing_intro: "Add your supplements and medications first.",
      msg_analyzing: "Analyzing", msg_items: "items…",
      msg_unreachable: "Server unreachable — is the backend running?",
      msg_no_interactions: "No known interactions",
      msg_none_found: "✓ No documented interactions were found among these items.",
      msg_queue_clear: "✓ Queue clear — nothing left to review.",
      status_major: "major", status_moderate: "moderate", status_minor: "minor",
      status_evidence: "Evidence-based", status_watch: "watch", status_avoid: "avoid", status_caution: "caution",
      summary_major: "serious warning", summary_warnings_found: "found",
      summary_may_deplete: "May deplete",
      age_placeholder: "Age (optional — enables Beers & QT risk checks)",
      timing_note: "Timing: you take these at different times of day — separating doses by 2+ hours reduces this risk.",
      fda_extra: "Information above is an automated reference from public databases, not medical advice. Consult a licensed physician or pharmacist.",
      privacy: "Privacy: your product list never leaves this browser. No account, no tracking."
    },
    vi: {
      tab_scan: "Quét sản phẩm", tab_cabinet: "Tủ thuốc", tab_check: "Kiểm tra", tab_review: "Duyệt",
      btn_start_camera: "Bật camera", btn_lookup: "Tra mã", btn_ocr: "Quét chữ trên nhãn (OCR)",
      btn_search: "Tìm kiếm", btn_check_interactions: "Kiểm tra tương tác", btn_print: "In / Lưu PDF",
      btn_verify: "✓ Xác nhận", btn_reject: "✗ Loại bỏ", btn_add: "Thêm",
      title_scan_product: "Quét sản phẩm", title_manual_add: "Thêm thủ công",
      title_cabinet: "Tủ thuốc của tôi", title_review_queue: "Hàng chờ duyệt",
      title_unmatched: "Không nhận dạng được", title_depletions: "Cảnh báo cạn kiệt dinh dưỡng",
      title_cascades: "Chuỗi rủi ro ẩn", title_qt: "Nguy cơ kéo dài khoảng QT",
      title_elytes: "Cảnh báo điện giải", title_beers: "Tiêu chuẩn Beers (từ 65 tuổi)",
      title_schedule: "Gợi ý lịch uống",
      scan_intro: "Hướng camera vào mã vạch hoặc nhập thủ công.",
      cabinet_intro: "TPCN và thuốc của bạn chỉ được lưu trong trình duyệt này.",
      review_intro: "Duyệt bởi dược sĩ cho các tương tác suy luận (tin cậy 0.5). Xác nhận hoặc loại.",
      unmatched_intro: "Các mục sau không được nhận dạng — kiểm tra chính tả hoặc thêm qua tìm kiếm:",
      depletions_intro: "Các thuốc này có thể làm cạn kiệt dinh dưỡng theo thời gian — nên trao đổi bổ sung với bác sĩ.",
      cascades_intro: "Suy luận từ đường dẫn enzyme — tín hiệu theo cơ chế, không phải tương tác được ghi nhận trực tiếp.",
      qt_intro: "Kết hợp nhiều thuốc kéo dài QT làm tăng nguy cơ rối loạn nhịp nguy hiểm (torsades).",
      elytes_intro: "Các thuốc này có thể làm mất kali/magie — nên xét nghiệm máu định kỳ.",
      beers_intro: "AGS Beers 2023 — thuốc cần thận trọng ở người cao tuổi.",
      schedule_intro: "Xung đột hấp thu — tách giờ uống làm giảm rủi ro.",
      msg_nothing: "Chưa có gì để kiểm tra", msg_nothing_intro: "Hãy thêm thực phẩm chức năng và thuốc của bạn trước.",
      msg_analyzing: "Đang phân tích", msg_items: "mục…",
      msg_unreachable: "Không kết nối được máy chủ — backend đang chạy chưa?",
      msg_no_interactions: "Không có tương tác đã ghi nhận",
      msg_none_found: "✓ Không tìm thấy tương tác nào được ghi nhận giữa các mục này.",
      msg_queue_clear: "✓ Hàng chờ trống — không còn gì để duyệt.",
      status_major: "nghiêm trọng", status_moderate: "trung bình", status_minor: "nhẹ",
      status_evidence: "Dựa trên bằng chứng", status_watch: "theo dõi", status_avoid: "tránh", status_caution: "thận trọng",
      summary_major: "cảnh báo nghiêm trọng", summary_warnings_found: "được phát hiện",
      summary_may_deplete: "Có thể làm cạn kiệt",
      age_placeholder: "Tuổi (tùy chọn — bật kiểm tra Beers & QT)",
      timing_note: "Thời điểm: bạn uống các thuốc này ở khung giờ khác nhau — cách nhau 2+ giờ giúp giảm rủi ro.",
      fda_extra: "Thông tin trên là tra cứu tự động từ cơ sở dữ liệu công khai, không phải tư vấn y tế. Hãy tham khảo bác sĩ hoặc dược sĩ.",
      privacy: "Riêng tư: danh sách sản phẩm không rời trình duyệt của bạn. Không tài khoản, không theo dõi."
    },
    fr: {
      tab_scan: "Scanner", tab_cabinet: "Mon armoire", tab_check: "Vérifier", tab_review: "Révision",
      btn_start_camera: "Démarrer la caméra", btn_lookup: "Rechercher", btn_ocr: "Scanner le texte (OCR)",
      btn_search: "Rechercher", btn_check_interactions: "Vérifier les interactions", btn_print: "Imprimer / PDF",
      btn_verify: "✓ Valider", btn_reject: "✗ Rejeter", btn_add: "Ajouter",
      title_scan_product: "Scanner un produit", title_manual_add: "Ajout manuel",
      title_cabinet: "Mon armoire", title_review_queue: "File de révision",
      title_unmatched: "Non identifié", title_depletions: "Surveillance des carences",
      title_cascades: "Chaînes de risque cachées", title_qt: "Risque d'allongement du QT",
      title_elytes: "Surveillance des électrolytes", title_beers: "Critères de Beers (65+)",
      title_schedule: "Suggestions d'horaires",
      scan_intro: "Visez le code-barres ou saisissez-le manuellement.",
      cabinet_intro: "Vos compléments et médicaments sont stockés uniquement dans ce navigateur.",
      review_intro: "Triage pharmacien des interactions inférées (confiance 0.5). Valider ou rejeter.",
      unmatched_intro: "Éléments non reconnus — vérifiez l'orthographe ou ajoutez-les via la recherche :",
      depletions_intro: "Ces médicaments peuvent épuiser des nutriments — à discuter avec votre médecin.",
      cascades_intro: "Déduit des voies enzymatiques — signal mécanistique, pas une interaction documentée.",
      qt_intro: "Combiner des médicaments allongeant le QT augmente le risque de torsades.",
      elytes_intro: "Ces médicaments peuvent épuiser potassium/magnésium — un bilan sanguin occasionnel est utile.",
      beers_intro: "Critères de Beers 2023 — médicaments à prudence chez les personnes âgées.",
      schedule_intro: "Conflits d'absorption — espacer les prises neutralise ces risques.",
      msg_nothing: "Rien à vérifier pour l'instant", msg_nothing_intro: "Ajoutez d'abord vos compléments et médicaments.",
      msg_analyzing: "Analyse de", msg_items: "éléments…",
      msg_unreachable: "Serveur injoignable — le backend tourne-t-il ?",
      msg_no_interactions: "Aucune interaction connue",
      msg_none_found: "✓ Aucune interaction documentée trouvée entre ces éléments.",
      msg_queue_clear: "✓ File vide — rien à réviser.",
      status_major: "majeure", status_moderate: "modérée", status_minor: "mineure",
      status_evidence: "Basé sur des preuves", status_watch: "surveiller", status_avoid: "éviter", status_caution: "prudence",
      summary_major: "avertissement grave", summary_warnings_found: "trouvé(s)",
      summary_may_deplete: "Peut épuiser",
      age_placeholder: "Âge (optionnel — active Beers & QT)",
      timing_note: "Horaire : vous les prenez à des moments différents — espacer de 2 h+ réduit ce risque.",
      fda_extra: "Les informations ci-dessus sont une référence automatisée issue de bases publiques, pas un avis médical.",
      privacy: "Confidentialité : votre liste ne quitte jamais ce navigateur. Aucun compte, aucun traçage."
    },
    de: {
      tab_scan: "Scannen", tab_cabinet: "Mein Schrank", tab_check: "Prüfen", tab_review: "Prüfung",
      btn_start_camera: "Kamera starten", btn_lookup: "Nachschlagen", btn_ocr: "Etikettentext scannen (OCR)",
      btn_search: "Suchen", btn_check_interactions: "Interaktionen prüfen", btn_print: "Drucken / PDF",
      btn_verify: "✓ Bestätigen", btn_reject: "✗ Ablehnen", btn_add: "Hinzufügen",
      title_scan_product: "Produkt scannen", title_manual_add: "Manuell hinzufügen",
      title_cabinet: "Mein Medikamentenschrank", title_review_queue: "Prüfwarteschlange",
      title_unmatched: "Nicht erkannt", title_depletions: "Nährstoffmangel-Warnung",
      title_cascades: "Versteckte Risikoketten", title_qt: "QT-Verlängerungsrisiko",
      title_elytes: "Elektrolyt-Watch", title_beers: "Beers-Kriterien (ab 65)",
      title_schedule: "Einnahmezeit-Empfehlungen",
      scan_intro: "Kamera auf den Barcode richten oder manuell eingeben.",
      cabinet_intro: "Ihre Präparate werden nur in diesem Browser gespeichert.",
      review_intro: "Apotheker-Sichtung abgeleiteter Interaktionen (Vertrauen 0,5). Bestätigen oder ablehnen.",
      unmatched_intro: "Diese Elemente wurden nicht erkannt — Schreibweise prüfen oder per Suche hinzufügen:",
      depletions_intro: "Diese Medikamente können Nährstoffe erschöpfen — mit dem Arzt besprechen.",
      cascades_intro: "Aus Enzymwegen abgeleitet — mechanistisches Signal, keine dokumentierte Interaktion.",
      qt_intro: "Die Kombination QT-verlängernder Medikamente erhöht das Torsades-Risiko.",
      elytes_intro: "Diese Medikamente können Kalium/Magnesium senken — gelegentliche Blutkontrolle sinnvoll.",
      beers_intro: "AGS-Beers-Kriterien 2023 — Vorsicht bei älteren Erwachsenen.",
      schedule_intro: "Resorptionskonflikte — zeitlicher Abstand entschärft diese.",
      msg_nothing: "Noch nichts zu prüfen", msg_nothing_intro: "Fügen Sie zuerst Ihre Präparate hinzu.",
      msg_analyzing: "Analysiere", msg_items: "Elemente…",
      msg_unreachable: "Server nicht erreichbar — läuft das Backend?",
      msg_no_interactions: "Keine bekannten Interaktionen",
      msg_none_found: "✓ Keine dokumentierten Interaktionen zwischen diesen Elementen gefunden.",
      msg_queue_clear: "✓ Warteschlange leer — nichts zu prüfen.",
      status_major: "schwer", status_moderate: "mittel", status_minor: "leicht",
      status_evidence: "Evidenzbasiert", status_watch: "beobachten", status_avoid: "meiden", status_caution: "Vorsicht",
      summary_major: "schwere Warnung", summary_warnings_found: "gefunden",
      summary_may_deplete: "Kann erschöpfen",
      age_placeholder: "Alter (optional — aktiviert Beers & QT)",
      timing_note: "Zeitplan: Sie nehmen diese zu unterschiedlichen Zeiten ein — 2+ Stunden Abstand reduziert das Risiko.",
      fda_extra: "Die obigen Informationen sind automatisierte Referenzen aus öffentlichen Datenbanken, kein medizinischer Rat.",
      privacy: "Datenschutz: Ihre Liste verlässt diesen Browser nie. Kein Konto, kein Tracking."
    },
    it: {
      tab_scan: "Scansiona", tab_cabinet: "La mia dispensa", tab_check: "Verifica", tab_review: "Revisione",
      btn_start_camera: "Avvia fotocamera", btn_lookup: "Cerca", btn_ocr: "Scansiona testo etichetta (OCR)",
      btn_search: "Cerca", btn_check_interactions: "Verifica interazioni", btn_print: "Stampa / PDF",
      btn_verify: "✓ Conferma", btn_reject: "✗ Rifiuta", btn_add: "Aggiungi",
      title_scan_product: "Scansiona un prodotto", title_manual_add: "Aggiungi manualmente",
      title_cabinet: "La mia dispensa", title_review_queue: "Coda di revisione",
      title_unmatched: "Non identificato", title_depletions: "Sorveglianza carenze nutrizionali",
      title_cascades: "Catene di rischio nascoste", title_qt: "Rischio allungamento QT",
      title_elytes: "Sorveglianza elettroliti", title_beers: "Criteri di Beers (65+)",
      title_schedule: "Suggerimenti di orari",
      scan_intro: "Punta la fotocamera sul codice a barre o inseriscilo manualmente.",
      cabinet_intro: "I tuoi integratori e farmaci sono salvati solo in questo browser.",
      review_intro: "Triage del farmacista per interazioni inferite (affidabilità 0.5). Conferma o rifiuta.",
      unmatched_intro: "Elementi non riconosciuti — controlla la grafia o aggiungili tramite ricerca:",
      depletions_intro: "Questi farmaci possono esaurire i nutrienti — vale la pena parlarne con il medico.",
      cascades_intro: "Dedotto dai pathway enzimatici — segnale meccanicistico, non un'interazione documentata.",
      qt_intro: "Combinare farmaci che allungano il QT aumenta il rischio di torsioni.",
      elytes_intro: "Questi farmaci possono esaurire potassio/magnesio — utile un esame del sangue periodico.",
      beers_intro: "Criteri di Beers 2023 — farmaci da usare con cautela negli anziani.",
      schedule_intro: "Conflitti di assorbimento — distanziare le dosi li neutralizza.",
      msg_nothing: "Niente da verificare", msg_nothing_intro: "Aggiungi prima integratori e farmaci.",
      msg_analyzing: "Analisi di", msg_items: "elementi…",
      msg_unreachable: "Server non raggiungibile — il backend è in esecuzione?",
      msg_no_interactions: "Nessuna interazione nota",
      msg_none_found: "✓ Nessuna interazione documentata trovata tra questi elementi.",
      msg_queue_clear: "✓ Coda vuota — niente da revisionare.",
      status_major: "maggiore", status_moderate: "moderata", status_minor: "minore",
      status_evidence: "Basato su evidenze", status_watch: "sorveglia", status_avoid: "evitare", status_caution: "cauzione",
      summary_major: "avviso grave", summary_warnings_found: "trovati",
      summary_may_deplete: "Può esaurire",
      age_placeholder: "Età (opzionale — attiva Beers e QT)",
      timing_note: "Orari: li assumi in momenti diversi — distanziare di 2+ ore riduce il rischio.",
      fda_extra: "Le informazioni sopra sono riferimenti automatici da banche dati pubbliche, non consulenza medica.",
      privacy: "Privacy: la tua lista non lascia mai questo browser. Nessun account, nessun tracciamento."
    },
    es: {
      tab_scan: "Escanear", tab_cabinet: "Mi armario", tab_check: "Comprobar", tab_review: "Revisión",
      btn_start_camera: "Iniciar cámara", btn_lookup: "Buscar", btn_ocr: "Escanear texto (OCR)",
      btn_search: "Buscar", btn_check_interactions: "Comprobar interacciones", btn_print: "Imprimir / PDF",
      btn_verify: "✓ Verificar", btn_reject: "✗ Rechazar", btn_add: "Añadir",
      title_scan_product: "Escanear un producto", title_manual_add: "Añadir manualmente",
      title_cabinet: "Mi armario", title_review_queue: "Cola de revisión",
      title_unmatched: "No identificado", title_depletions: "Vigilancia de depleción nutricional",
      title_cascades: "Cadenas de riesgo ocultas", title_qt: "Riesgo de prolongación del QT",
      title_elytes: "Vigilancia de electrolitos", title_beers: "Criterios de Beers (65+)",
      title_schedule: "Sugerencias de horario",
      scan_intro: "Apunta la cámara al código de barras o introdúcelo manualmente.",
      cabinet_intro: "Tus suplementos y medicamentos se guardan solo en este navegador.",
      review_intro: "Clasificación farmacéutica de interacciones inferidas (confianza 0.5). Verificar o rechazar.",
      unmatched_intro: "Estos elementos no se reconocieron — revisa la ortografía o añádelos mediante búsqueda:",
      depletions_intro: "Estos medicamentos pueden agotar nutrientes — vale la pena comentarlo con tu médico.",
      cascades_intro: "Inferido de vías enzimáticas — señal mecanicista, no una interacción documentada.",
      qt_intro: "Combinar fármacos que prolongan el QT aumenta el riesgo de torsades.",
      elytes_intro: "Estos medicamentos pueden agotar potasio/magnesio — conviene un análisis de sangre ocasional.",
      beers_intro: "Criterios de Beers 2023 — medicamentos que requieren precaución en adultos mayores.",
      schedule_intro: "Conflictos de absorción — espaciar las dosis los neutraliza.",
      msg_nothing: "Nada que comprobar aún", msg_nothing_intro: "Añade primero tus suplementos y medicamentos.",
      msg_analyzing: "Analizando", msg_items: "elementos…",
      msg_unreachable: "Servidor inaccesible — ¿está corriendo el backend?",
      msg_no_interactions: "Sin interacciones conocidas",
      msg_none_found: "✓ No se encontraron interacciones documentadas entre estos elementos.",
      msg_queue_clear: "✓ Cola vacía — nada que revisar.",
      status_major: "grave", status_moderate: "moderada", status_minor: "leve",
      status_evidence: "Basado en evidencia", status_watch: "vigilar", status_avoid: "evitar", status_caution: "precaución",
      summary_major: "advertencia grave", summary_warnings_found: "encontradas",
      summary_may_deplete: "Puede agotar",
      age_placeholder: "Edad (opcional — activa Beers y QT)",
      timing_note: "Horario: los tomas a distintas horas — separarlos 2+ horas reduce este riesgo.",
      fda_extra: "La información anterior es una referencia automatizada de bases de datos públicas, no consejo médico.",
      privacy: "Privacidad: tu lista nunca sale de este navegador. Sin cuenta, sin rastreo."
    }
  };

  const LANGS = [
    { code: "en", label: "🇺🇸 EN" }, { code: "vi", label: "🇻🇳 VI" }, { code: "fr", label: "🇫🇷 FR" },
    { code: "de", label: "🇩🇪 DE" }, { code: "it", label: "🇮🇹 IT" }, { code: "es", label: "🇪🇸 ES" }
  ];
  const STORE_KEY = "medmatch_lang";

  function currentLang() {
    return localStorage.getItem(STORE_KEY) || "en";
  }

  function t(key, fallback) {
    const dict = DICTS[I18N.lang] || DICTS.en;
    if (dict[key]) return dict[key];
    if (DICTS.en[key]) return DICTS.en[key];
    return fallback || key;
  }

  function applyStatic() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const original = el.getAttribute("data-i18n-fb") || el.textContent;
      if (!el.hasAttribute("data-i18n-fb")) el.setAttribute("data-i18n-fb", original);
      el.textContent = t(key, original);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      const original = el.getAttribute("data-i18n-ph-fb") || el.placeholder;
      if (!el.hasAttribute("data-i18n-ph-fb")) el.setAttribute("data-i18n-ph-fb", original);
      el.placeholder = t(key, original);
    });
  }

  const I18N = {
    get lang() { return currentLang(); },
    langs: LANGS,
    t,
    setLang(code) {
      if (!DICTS[code]) return;
      localStorage.setItem(STORE_KEY, code);
      const sel = document.getElementById("lang-select");
      if (sel) sel.value = code;
      applyStatic();
      document.dispatchEvent(new CustomEvent("medmatch:lang"));
    }
  };

  window.I18N = I18N;

  document.addEventListener("DOMContentLoaded", () => {
    const sel = document.getElementById("lang-select");
    if (sel) {
      sel.innerHTML = LANGS.map((l) => `<option value="${l.code}">${l.label}</option>`).join("");
      sel.value = currentLang();
      sel.addEventListener("change", () => I18N.setLang(sel.value));
    }
    applyStatic();
  });
})();
