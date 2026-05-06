export interface UserDisplayLike {
  real_name?: string | null;
  username?: string | null;
}

export const getUserDisplayName = (user?: UserDisplayLike | null, fallback = '-') => {
  const realName = user?.real_name?.trim();
  if (realName) {
    return realName;
  }

  const username = user?.username?.trim();
  if (username) {
    return username;
  }

  return fallback;
};
