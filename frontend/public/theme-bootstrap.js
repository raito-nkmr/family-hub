;(() => {
  try {
    const savedTheme = localStorage.getItem('family-hub-theme')
    const theme =
      savedTheme === 'light' || savedTheme === 'dark'
        ? savedTheme
        : matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light'
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    localStorage.setItem('family-hub-theme', theme)
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', theme === 'dark' ? '#0b1726' : '#d8e2ed')
  } catch {
    document.documentElement.dataset.theme = 'light'
    document.documentElement.style.colorScheme = 'light'
  }
})()
