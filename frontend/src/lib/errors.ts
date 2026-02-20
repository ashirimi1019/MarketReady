export class ApiError extends Error {
  public readonly status: number;
  public readonly body: string;

  constructor(status: number, body: string) {
    super(`API error ${status}: ${body}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function parseApiBody(body: string): unknown {
  try {
    return JSON.parse(body);
  } catch {
    return null;
  }
}

export function isAuthError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 401;
}

export function isNotFound(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 404;
}

export function isRateLimited(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 429;
}

export function isServerError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status >= 500;
}

export function isValidationError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 400;
}

export function isForbidden(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 403;
}

export function isConflict(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 409;
}

/**
 * Extract a user-friendly message from an error.
 * Attempts to parse the FastAPI {"detail": "..."} format.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const parsed = parseApiBody(error.body);
    if (parsed && typeof parsed === "object") {
      const detail = (parsed as { detail?: unknown }).detail;
      const message = (parsed as { message?: unknown }).message;
      if (typeof detail === "string") return detail;
      if (detail && typeof detail === "object") {
        const detailMessage = (detail as { message?: unknown }).message;
        if (typeof detailMessage === "string") return detailMessage;
      }
      if (typeof message === "string") return message;
    }
    return error.body || error.message;
  }
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}

export function getRetryAfterSeconds(error: unknown): number | null {
  if (!(error instanceof ApiError)) return null;
  const parsed = parseApiBody(error.body);
  if (!parsed || typeof parsed !== "object") return null;
  const detail = (parsed as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return null;
  const retry = (detail as { retry_after_seconds?: unknown }).retry_after_seconds;
  return typeof retry === "number" ? retry : null;
}
