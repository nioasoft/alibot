export function getTrackingAdminCredentials() {
  const username = process.env.TRACKING_ADMIN_USERNAME?.trim();
  const password = process.env.TRACKING_ADMIN_PASSWORD?.trim();

  if (!username || !password) {
    return null;
  }

  return { username, password };
}

export function hasValidBasicAuthHeader(
  authorizationHeader: string | null
): boolean {
  const credentials = getTrackingAdminCredentials();
  if (!credentials || !authorizationHeader?.startsWith("Basic ")) {
    return false;
  }

  try {
    const encodedCredentials = authorizationHeader.slice(6).trim();
    const decoded = atob(encodedCredentials);
    const separatorIndex = decoded.indexOf(":");

    if (separatorIndex < 0) {
      return false;
    }

    const username = decoded.slice(0, separatorIndex);
    const password = decoded.slice(separatorIndex + 1);

    return (
      username === credentials.username && password === credentials.password
    );
  } catch {
    return false;
  }
}
