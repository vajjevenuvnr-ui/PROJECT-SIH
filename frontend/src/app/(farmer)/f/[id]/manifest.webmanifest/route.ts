// Web app manifest per panchayat, so "Add to Home screen" opens this farmer's own page.
// Manifests need literal colours; these must match --color-primary / --color-background in theme.css.
export function GET(_req: Request, { params }: { params: { id: string } }) {
  const id = Number(params.id) || 0;
  return Response.json(
    {
      name: "Kshetra",
      short_name: "Kshetra",
      description: "Village weather and farm advice",
      start_url: `/f/${id}`,
      scope: "/f/",
      display: "standalone",
      background_color: "#F7FAF9",
      theme_color: "#0B5D4B",
      icons: [
        { src: "/brand/icon-192.png", sizes: "192x192", type: "image/png" },
        { src: "/brand/icon-512.png", sizes: "512x512", type: "image/png" },
      ],
    },
    { headers: { "Content-Type": "application/manifest+json" } },
  );
}
