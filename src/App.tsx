import BlurText from '@/components/BlurText/BlurText'
import SplitText from '@/components/SplitText/SplitText'
import { useSmoothScroll } from '@/hooks/useLenis'

function App() {
  useSmoothScroll()

  return (
    <main className="bg-neutral-950 text-neutral-100">
      <section className="flex min-h-screen items-center justify-center px-4">
        <SplitText text="Music-AI" tag="h1" className="text-6xl font-bold" trigger="load" />
      </section>
      <section className="flex min-h-screen items-center justify-center px-4">
        <BlurText text="GSAP + Lenis + React Bits" className="text-4xl" animateBy="words" />
      </section>
    </main>
  )
}

export default App
