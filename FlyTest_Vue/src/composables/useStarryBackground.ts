import { onMounted, onUnmounted, type Ref } from 'vue'

interface Star {
  x: number
  y: number
  size: number
  opacity: number
  twinkleSpeed: number
  twinklePhase: number
}

interface Meteor {
  x: number
  y: number
  length: number
  speed: number
  opacity: number
  angle: number
  thickness: number
  life: number
  maxLife: number
}

export function useStarryBackground(canvasRef: Ref<HTMLCanvasElement | null>) {
  let animationId: number
  let stars: Star[] = []
  let meteors: Meteor[] = []
  let ctx: CanvasRenderingContext2D | null = null
  let width = 0
  let height = 0

  function initCanvas() {
    const canvas = canvasRef.value
    if (!canvas) return
    ctx = canvas.getContext('2d')
    resize()
    initStars()
  }

  function resize() {
    const canvas = canvasRef.value
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    width = window.innerWidth
    height = window.innerHeight
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
    ctx?.scale(dpr, dpr)
  }

  function initStars() {
    const count = Math.floor((width * height) / 2000)
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 1.8 + 0.3,
      opacity: Math.random() * 0.8 + 0.2,
      twinkleSpeed: Math.random() * 0.02 + 0.005,
      twinklePhase: Math.random() * Math.PI * 2,
    }))
  }

  function spawnMeteor() {
    const angle = Math.PI / 2 + (Math.random() - 0.5) * 0.3
    meteors.push({
      x: Math.random() * width * 1.2 - width * 0.1,
      y: -20,
      length: Math.random() * 120 + 60,
      speed: Math.random() * 4 + 3,
      opacity: Math.random() * 0.6 + 0.4,
      angle,
      thickness: Math.random() * 1.5 + 0.5,
      life: 0,
      maxLife: Math.random() * 120 + 80,
    })
  }

  function drawStars(time: number) {
    if (!ctx) return
    for (const star of stars) {
      const flicker = Math.sin(time * star.twinkleSpeed + star.twinklePhase)
      const alpha = star.opacity * (0.6 + 0.4 * flicker)
      ctx.beginPath()
      ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`
      ctx.fill()
    }
  }

  function drawMeteors() {
    if (!ctx) return
    meteors = meteors.filter((m) => {
      m.life++
      m.x += Math.cos(m.angle) * m.speed
      m.y += Math.sin(m.angle) * m.speed

      const fadeRatio = 1 - m.life / m.maxLife
      if (fadeRatio <= 0 || m.y > height + 50) return false

      const alpha = m.opacity * fadeRatio
      const tailX = m.x - Math.cos(m.angle) * m.length
      const tailY = m.y - Math.sin(m.angle) * m.length

      const grad = ctx!.createLinearGradient(m.x, m.y, tailX, tailY)
      grad.addColorStop(0, `rgba(255, 255, 255, ${alpha})`)
      grad.addColorStop(0.3, `rgba(200, 220, 255, ${alpha * 0.5})`)
      grad.addColorStop(1, 'rgba(200, 220, 255, 0)')

      ctx!.beginPath()
      ctx!.moveTo(tailX, tailY)
      ctx!.lineTo(m.x, m.y)
      ctx!.strokeStyle = grad
      ctx!.lineWidth = m.thickness
      ctx!.lineCap = 'round'
      ctx!.stroke()

      // 头部发光
      ctx!.beginPath()
      ctx!.arc(m.x, m.y, m.thickness + 1, 0, Math.PI * 2)
      ctx!.fillStyle = `rgba(255, 255, 255, ${alpha * 0.8})`
      ctx!.fill()

      return true
    })
  }

  function animate(time: number) {
    if (!ctx) return
    ctx.clearRect(0, 0, width, height)

    drawStars(time)

    if (Math.random() < 0.06) spawnMeteor()
    drawMeteors()

    animationId = requestAnimationFrame(animate)
  }

  function handleResize() {
    resize()
    initStars()
  }

  onMounted(() => {
    initCanvas()
    animationId = requestAnimationFrame(animate)
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    cancelAnimationFrame(animationId)
    window.removeEventListener('resize', handleResize)
  })
}
