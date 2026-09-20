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
  | "process:write";

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
