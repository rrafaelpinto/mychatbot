// Public shapes mirror /api/schema/. Refresh with "npm run api:types" when the API changes.
export type PublicFact = { id: number; fact_type: string; content: string };
export type CandidateSummary = {
  slug: string;
  name: string;
  professional_summary: string;
  image_url: string;
  linkedin: string | null;
  contact_email: string | null;
};
export type CandidateDetail = CandidateSummary & { facts: PublicFact[] };
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type TokenResponse = { access: string; token_type: "Bearer"; expires_in: number };
export type ChatMessage = { role: "user" | "assistant"; content: string; evidence: PublicFact[] };
export type ChatAnswer = { response: string; evidence: PublicFact[] };

export type OwnerProfile = {
  slug: string;
  name: string;
  professional_summary: string;
  image_url: string;
  linkedin: string;
  show_linkedin: boolean;
  contact_email: string;
  show_contact_email: boolean;
  status: string;
  publication_status: string;
};
export type OwnerProfileUpdate = Pick<OwnerProfile, "name" | "professional_summary" | "linkedin" | "show_linkedin" | "contact_email" | "show_contact_email">;
export type OwnerFact = {
  id: number;
  fact_type: string;
  content: string;
  verification_status: "pending" | "verified" | "rejected";
  is_public: boolean;
  updated_at: string;
};
export type ReviewAction = "approve" | "reject" | "reopen" | "publish" | "unpublish";
