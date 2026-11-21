/** Untrusted, source-bounded research-content extraction response. */

import { MAX_PDF_BYTES } from "./document";

export const FACETS = [
  { key: "aim", label: "Research aim" },
  { key: "method", label: "Study design / method" },
  { key: "sample", label: "Sample / participants" },
  { key: "instruments", label: "Scales / measures" },
  { key: "findings", label: "Main findings" },
  { key: "limitations", label: "Limitations" },
] as const;

export type LiteratureFacet = (typeof FACETS)[number]["key"];
export type FindingStatus = "grounded" | "not_identified" | "rejected_quote";

export interface LiteratureFinding {
  facet: LiteratureFacet;
  status: FindingStatus;
  value: string | null;
  quote: string | null;
  locator: string | null;
}

export interface LiteratureProfile {
  document_title: string;
  sha256: string;
  page_count: number;
  text_page_count: number;
  model: string;
  findings: LiteratureFinding[];
  caveat: string;
}

export function validateLiteratureUpload(
  file: Pick<File, "name" | "size"> | null,
  consent: boolean,
): string | null {
  if (!file) return "Choose a PDF document.";
  if (!file.name.toLowerCase().endsWith(".pdf")) return "Only PDF documents are supported.";
  if (file.size === 0 || file.size > MAX_PDF_BYTES)
    return "PDF must be nonempty and at most 8 MiB.";
  if (!consent) return "Please confirm before sending selected PDF excerpts to Groq.";
  return null;
}

export function isLiteratureProfile(value: unknown): value is LiteratureProfile {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const report = value as Partial<LiteratureProfile>;
  return typeof report.document_title === "string"
    && typeof report.sha256 === "string"
    && typeof report.page_count === "number"
    && typeof report.model === "string"
    && typeof report.caveat === "string"
    && Array.isArray(report.findings)
    && report.findings.length === FACETS.length
    && FACETS.every(({ key }) => report.findings?.some((f) =>
      f && f.facet === key
      && ["grounded", "not_identified", "rejected_quote"].includes(f.status)
      && (f.value === null || typeof f.value === "string")
      && (f.quote === null || typeof f.quote === "string")
      && (f.locator === null || typeof f.locator === "string")
    ));
}

function csvCell(value: string): string {
  // User PDFs and model output are untrusted; never export active spreadsheet formulas.
  const safe = /^[\s]*[=+@-]/.test(value) ? "'" + value : value;
  return '"' + safe.replaceAll('"', '""') + '"';
}

export function literatureProfileCsv(profiles: LiteratureProfile[]): string {
  const headers = [
    "Document", "SHA256", "Total PDF pages", "Text pages",
    ...FACETS.flatMap(({ label }) => [
      label, label + " status", label + " page locator", label + " exact quote",
    ]),
  ];
  const rows = profiles.map((p) => [
    p.document_title, p.sha256, String(p.page_count), String(p.text_page_count),
    ...FACETS.flatMap(({ key }) => {
      const field = p.findings.find((item) => item.facet === key);
      return [
        field?.value || "", field?.status || "not_identified",
        field?.locator || "", field?.quote || "",
      ];
    }),
  ]);
  return [headers, ...rows]
    .map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}
