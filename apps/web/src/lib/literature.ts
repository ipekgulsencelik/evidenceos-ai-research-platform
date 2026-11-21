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
export type RejectionReason =
  | "duplicate_field" | "incomplete_evidence" | "quote_not_found"
  | "ambiguous_location" | "invalid_length";

export interface HumanReview {
  corrected_value: string;
  note: string;
  reviewed: boolean;
}
export type HumanReviews = Record<string, HumanReview>;
export type FacetFilter = LiteratureFacet | "all";
export type StatusFilter = FindingStatus | "all";
export interface MatrixFilters {
  query: string;
  facet: FacetFilter;
  status: StatusFilter;
}
export interface MatrixRow {
  profile: LiteratureProfile;
  finding: LiteratureFinding;
  key: string;
}


export interface LiteratureFinding {
  facet: LiteratureFacet;
  status: FindingStatus;
  value: string | null;
  quote: string | null;
  locator: string | null;
  rejection_reason: RejectionReason | null;
  locator_repaired: boolean;
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

export const REJECTION_MESSAGES: Record<RejectionReason, string> = {
  duplicate_field: "The model returned multiple values for this field; neither was trusted.",
  incomplete_evidence: "The model did not provide both an interpretation and an exact quote.",
  quote_not_found: "The proposed quotation is not verbatim in any selected PDF excerpt.",
  ambiguous_location: "The exact quotation occurs on multiple pages without a valid reference.",
  invalid_length: "The proposed value or quotation failed length checks.",
};

export function reviewKey(sha256: string, facet: LiteratureFacet): string {
  return sha256 + ":" + facet;
}

export function selectMatrixRows(
  profiles: LiteratureProfile[],
  reviews: HumanReviews,
  filters: MatrixFilters,
): MatrixRow[] {
  const query = filters.query.trim().toLocaleLowerCase();
  return profiles.flatMap((profile) =>
    profile.findings.filter((finding) => {
      if (filters.facet !== "all" && finding.facet !== filters.facet) return false;
      if (filters.status !== "all" && finding.status !== filters.status) return false;
      const review = reviews[reviewKey(profile.sha256, finding.facet)];
      const match = [
        profile.document_title,
        finding.value || "",
        finding.quote || "",
        finding.locator || "",
        review?.corrected_value || "",
        review?.note || "",
      ].join(" ").toLocaleLowerCase();
      return !query || match.includes(query);
    }).map((finding) => ({
      profile, finding, key: reviewKey(profile.sha256, finding.facet),
    })),
  );
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
      && (f.rejection_reason === null ||
          (typeof f.rejection_reason === "string" && f.rejection_reason in REJECTION_MESSAGES))
      && typeof f.locator_repaired === "boolean"
    ));
}

function csvCell(value: string): string {
  // User PDFs and model output are untrusted; never export active spreadsheet formulas.
  const safe = /^[\s]*[=+@-]/.test(value) ? "'" + value : value;
  return '"' + safe.replaceAll('"', '""') + '"';
}

export function literatureProfileCsv(
  profiles: LiteratureProfile[],
  reviews: HumanReviews = {},
): string {
  const headers = [
    "Document", "SHA256", "Total PDF pages", "Text pages",
    ...FACETS.flatMap(({ label }) => [
      label + " AI extracted value", label + " AI status",
      label + " page locator", label + " exact quote",
      label + " rejection reason", label + " locator repaired",
      label + " researcher correction (unverified)",
      label + " researcher note", label + " reviewed against PDF",
    ]),
  ];
  const rows = profiles.map((profile) => [
    profile.document_title, profile.sha256, String(profile.page_count),
    String(profile.text_page_count),
    ...FACETS.flatMap(({ key }) => {
      const finding = profile.findings.find((f) => f.facet === key);
      const review = reviews[reviewKey(profile.sha256, key)];
      return [
        finding?.value || "", finding?.status || "not_identified",
        finding?.locator || "", finding?.quote || "",
        finding?.rejection_reason || "", finding?.locator_repaired ? "yes" : "no",
        review?.corrected_value || "", review?.note || "",
        review?.reviewed ? "yes" : "no",
      ];
    }),
  ]);
  return [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}
