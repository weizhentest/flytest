export function getPublicAssetUrl(assetPath: string): string {
  const normalizedPath = assetPath.replace(/^\/+/, '');
  return `${import.meta.env.BASE_URL}${normalizedPath}`;
}

export const brandLogoUrl = getPublicAssetUrl('logo.svg');
