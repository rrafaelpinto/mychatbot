import type { components } from "./schema.generated";

// Application types derive from the versioned Django OpenAPI schema.
export type PublicFact = components["schemas"]["PublicFact"];
export type CandidateSummary = components["schemas"]["PublicCandidate"];
export type CandidateDetail = components["schemas"]["PublicCandidateDetail"];
export type CandidateList = components["schemas"]["PaginatedPublicCandidateList"];
export type OwnerFactList = components["schemas"]["PaginatedOwnerFactList"];
export type TokenResponse = components["schemas"]["AccessToken"];
export type ChatMessage = components["schemas"]["CandidateChatHistory"];
export type ChatAnswer = components["schemas"]["CandidateChatOutput"];
export type OwnerProfile = components["schemas"]["OwnerCandidate"];
export type OwnerProfileUpdate = Required<components["schemas"]["PatchedOwnerProfileUpdateRequest"]>;
export type OwnerFact = components["schemas"]["OwnerFact"];
export type ReviewAction = components["schemas"]["ActionEnum"];
