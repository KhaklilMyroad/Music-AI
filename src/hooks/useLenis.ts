import { useEffect } from 'react'
import Lenis from 'lenis'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

// Smooth scrolling driven by GSAP's ticker so ScrollTrigger stays in sync.
export function useSmoothScroll() {
  useEffect(() => {
    const lenis = new Lenis()
    const off = lenis.on('scroll', ScrollTrigger.update)
    const tick = (time: number) => lenis.raf(time * 1000)

    gsap.ticker.add(tick)
    gsap.ticker.lagSmoothing(0)

    return () => {
      off()
      gsap.ticker.remove(tick)
      lenis.destroy()
    }
  }, [])
}
