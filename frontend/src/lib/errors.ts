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
    try {
      const parsed = JSON.parse(error.body);
      if (typeof parsed.detail === "string") return parsed.detail;
      if (typeof parsed.message === "string") return parsed.message;
    } catch {
      // body is not JSON
    }
    return error.body || error.message;
  }
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}
