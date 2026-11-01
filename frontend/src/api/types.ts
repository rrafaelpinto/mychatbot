import type { components } from "./schema.generated";

// Application types derive from the versioned Django OpenAPI schema.
export type PublicFact = components["schemas"]["PublicFact"];
export type CandidateSummary = components["schemas"]["PublicCandidate"];
export type CandidateDetail = Omit<components["schemas"]["PublicCandidateDetail"], "facts"> & {
  readonly facts: PublicFact[];
};
export type Page<T> = Pick<components["schemas"]["PaginatedPublicCandidateList"], "count" | "next" | "previous"> & {
  results: T[];
};
export type TokenResponse = components["schemas"]["AccessToken"];
export type ChatMessage = components["schemas"]["CandidateChatHistory"];
export type ChatAnswer = components["schemas"]["CandidateChatOutput"];
export type OwnerProfile = components["schemas"]["OwnerCandidate"];
export type OwnerProfileUpdate = Required<components["schemas"]["PatchedOwnerProfileUpdateRequest"]>;
export type OwnerFact = components["schemas"]["OwnerFact"];
export type ReviewAction = components["schemas"]["ActionEnum"];
