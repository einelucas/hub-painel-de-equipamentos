export type Role = "VIEWER" | "ANALYST" | "ADMIN";

export type Permission =
  | "users:manage"
  | "audit:read"
  | "equipments:read"
  | "equipments:write"
  | "catalogs:read"
  | "catalogs:manage"
  | "workflow:read"
  | "workflow:transition"
  | "workflow:reopen"
  | "workflow:reopen_request"
  | "workflow:reopen_approve"
  | "process:write"
  | "suppliers:read"
  | "suppliers:write";

export interface CurrentUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  active: boolean;
  permissions?: Permission[];
}

export interface ApiProblem {
  detail?: string | Array<{ msg?: string }>;
  message?: string;
  error?: string;
}

export interface UserSummary {
  id: string;
  name: string;
  email: string;
  role: Role;
  active: boolean;
}
