import { NextRequest, NextResponse } from "next/server";
import { getTrackingAdminCredentials, hasValidBasicAuthHeader } from "@/lib/admin-auth";

export function middleware(request: NextRequest) {
  if (!request.nextUrl.pathname.startsWith("/admin")) {
    return NextResponse.next();
  }

  if (!getTrackingAdminCredentials()) {
    return new NextResponse("Missing tracking admin credentials", {
      status: 500,
    });
  }

  if (hasValidBasicAuthHeader(request.headers.get("authorization"))) {
    return NextResponse.next();
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="Tracking Admin", charset="UTF-8"',
      "Cache-Control": "no-store",
    },
  });
}

export const config = {
  matcher: ["/admin/:path*"],
};
