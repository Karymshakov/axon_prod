import { createFileRoute, Link, Navigate } from '@tanstack/react-router'
import { useAuth } from '@/contexts/auth-context'
import {
  ArrowRight,
  Bot,
  BarChart3,
  MessageSquare,
  BookOpen,
  Check,
  Zap,
  Target,
  TrendingUp,
  Users,
  Building2,
  Dumbbell,
  ShoppingCart,
  Sparkles,
  Shield,
  Globe,
  Activity,
  ChevronRight,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useEffect, useRef, useState, useCallback } from 'react'

export const Route = createFileRoute('/')({
  component: Home,
})

function Home() {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) return null
  if (isAuthenticated) return <Navigate to="/dashboard" />
  return <LandingPage />
}

// ---------------------------------------------------------------------------
// HOOKS
// ---------------------------------------------------------------------------

/** Adds `is-visible` class when element enters the viewport */
function useScrollReveal<T extends HTMLElement = HTMLElement>(
  options: IntersectionObserverInit = {}
) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add('is-visible')
          obs.unobserve(el)
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px', ...options }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return ref
}

/** Reveal multiple children with stagger */
function useStaggerReveal<T extends HTMLElement = HTMLElement>(
  count: number,
  options: IntersectionObserverInit = {}
) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const container = ref.current
    if (!container) return
    const items = container.querySelectorAll<HTMLElement>('.stagger-item')
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          items.forEach((item, i) => {
            setTimeout(() => item.classList.add('is-visible'), i * 120)
          })
          obs.unobserve(container)
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -30px 0px', ...options }
    )
    obs.observe(container)
    return () => obs.disconnect()
  }, [count])
  return ref
}

/** Animates a number from 0 to target when element is visible */
function useCountUp(target: number, duration = 1800) {
  const [value, setValue] = useState(0)
  const ref = useRef<HTMLDivElement>(null)
  const started = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true
          const start = performance.now()
          const tick = (now: number) => {
            const p = Math.min((now - start) / duration, 1)
            const ease = 1 - Math.pow(1 - p, 4) // easeOutQuart
            setValue(Math.round(ease * target))
            if (p < 1) requestAnimationFrame(tick)
          }
          requestAnimationFrame(tick)
          obs.unobserve(el)
        }
      },
      { threshold: 0.5 }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [target, duration])

  return { ref, value }
}

/** Navbar shadow on scroll */
function useNavbarScroll() {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const onScroll = () => {
      if (!ref.current) return
      if (window.scrollY > 20) {
        ref.current.classList.add('navbar-scrolled')
      } else {
        ref.current.classList.remove('navbar-scrolled')
      }
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  return ref
}

// ---------------------------------------------------------------------------
// LANDING PAGE ROOT
// ---------------------------------------------------------------------------

function LandingPage() {
  return (
    <div
      className="bg-[#F8FAFF] text-gray-900 overflow-x-hidden"
      style={{ fontFamily: "'Inter', system-ui, sans-serif", colorScheme: 'light' }}
    >
      <Navbar />
      <Hero />
      <Features />
      <HowItWorks />
      <Industries />
      <AIAgentSpotlight />
      <CTASection />
      <Footer />
    </div>
  )
}

// ---------------------------------------------------------------------------
// NAVBAR
// ---------------------------------------------------------------------------

function Navbar() {
  const navRef = useNavbarScroll()
  return (
    <nav
      ref={navRef}
      className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-xl border-b border-black/[0.06] transition-all duration-300"
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <a href="#" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 bg-gradient-to-br from-[#2461FF] to-[#7C3AED] rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/25 group-hover:scale-110 transition-transform duration-300">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <span
              className="font-bold text-xl text-[#0A1628]"
              style={{ fontFamily: "'Ubuntu', sans-serif" }}
            >
              OmniOS
            </span>
          </a>
          <div className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-500">
            {[
              { label: 'Возможности', href: '#features' },
              { label: 'Как это работает', href: '#how-it-works' },
              { label: 'Отрасли', href: '#industries' },
              { label: 'ИИ-агент', href: '#ai-agent' },
            ].map(({ label, href }) => (
              <a
                key={href}
                href={href}
                className="hover:text-slate-900 transition-colors relative after:absolute after:bottom-0 after:left-0 after:h-px after:w-0 after:bg-[#2461FF] after:transition-all after:duration-300 hover:after:w-full pb-0.5"
              >
                {label}
              </a>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors hidden sm:block"
          >
            Войти
          </Link>
          <Link to="/register">
            <Button
              size="sm"
              className="shimmer-btn bg-gradient-to-r from-[#2461FF] to-[#7C3AED] hover:opacity-90 text-white border-0 shadow-lg shadow-blue-500/20 font-semibold transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-blue-500/30"
            >
              Начать бесплатно
            </Button>
          </Link>
        </div>
      </div>
    </nav>
  )
}

// ---------------------------------------------------------------------------
// HERO
// ---------------------------------------------------------------------------

function Hero() {
  const badgeRef = useScrollReveal()
  const h1Ref = useScrollReveal<HTMLHeadingElement>({ threshold: 0.1 })
  const subRef = useScrollReveal<HTMLParagraphElement>()
  const ctaRef = useScrollReveal<HTMLDivElement>()
  const mockupRef = useScrollReveal<HTMLDivElement>()

  return (
    <section className="relative pt-28 pb-16 overflow-hidden">
      {/* Animated gradient blobs */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div
          className="absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[600px] rounded-full blob-anim-1"
          style={{ background: 'radial-gradient(ellipse, rgba(36,97,255,0.12) 0%, transparent 70%)' }}
        />
        <div
          className="absolute -top-20 -right-40 w-[600px] h-[400px] rounded-full blob-anim-2"
          style={{ background: 'radial-gradient(ellipse, rgba(124,58,237,0.10) 0%, transparent 70%)' }}
        />
        <div
          className="absolute top-1/2 -left-40 w-[500px] h-[500px] rounded-full blob-anim-3"
          style={{ background: 'radial-gradient(ellipse, rgba(36,97,255,0.07) 0%, transparent 70%)' }}
        />
      </div>

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        {/* Badge */}
        <div className="flex justify-center mb-6">
          <div
            ref={badgeRef as React.Ref<HTMLDivElement>}
            className="badge-pulse scroll-reveal inline-flex items-center gap-1.5 bg-gradient-to-r from-blue-50 to-violet-50 text-blue-700 text-xs font-bold uppercase tracking-widest px-4 py-2 rounded-full border border-blue-200/60"
          >
            <Zap className="w-3 h-3 fill-current" />
            ИИ-CRM нового поколения
          </div>
        </div>

        {/* Headline */}
        <h1
          ref={h1Ref}
          className="scroll-reveal delay-100 text-center text-5xl md:text-6xl lg:text-[72px] font-bold text-[#0A1628] leading-[1.08] tracking-tight mb-6"
          style={{ fontFamily: "'Ubuntu', sans-serif" }}
        >
          CRM, которая{' '}
          <span className="bg-gradient-to-r from-[#2461FF] via-[#5B8EFF] to-[#7C3AED] bg-clip-text text-transparent">
            закрывает сделки
          </span>
          <br />
          пока вы спите
        </h1>

        {/* Subheadline */}
        <p
          ref={subRef as React.Ref<HTMLParagraphElement>}
          className="scroll-reveal delay-200 text-center text-lg md:text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed"
        >
          Автоматически отвечайте на заявки, квалифицируйте лидов и доводите их до
          оплаты — без участия менеджера
        </p>

        {/* CTAs */}
        <div
          ref={ctaRef as React.Ref<HTMLDivElement>}
          className="scroll-reveal delay-300 flex items-center justify-center gap-4 flex-wrap mb-4"
        >
          <Link to="/register">
            <Button
              size="lg"
              className="shimmer-btn h-12 px-8 text-base font-semibold bg-gradient-to-r from-[#2461FF] to-[#7C3AED] hover:opacity-90 text-white border-0 shadow-xl shadow-blue-500/25 transition-all duration-300 hover:scale-105 hover:shadow-2xl hover:shadow-blue-500/35 group"
            >
              Начать бесплатно
              <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Button>
          </Link>
          <Link to="/login">
            <Button
              variant="outline"
              size="lg"
              className="h-12 px-8 text-base font-medium border-slate-200 bg-white/70 hover:bg-white text-slate-700 transition-all duration-300 hover:scale-105 hover:border-slate-300 hover:shadow-lg"
            >
              Войти
              <ChevronRight className="ml-1 w-4 h-4 opacity-50" />
            </Button>
          </Link>
        </div>
        <p className="text-center text-sm text-slate-400 mb-16">
          Бесплатно · Без кредитной карты · Быстрая настройка
        </p>

        {/* Dashboard Mockup */}
        <div
          ref={mockupRef as React.Ref<HTMLDivElement>}
          className="scroll-reveal scale delay-400 relative max-w-5xl mx-auto"
        >
          <div
            className="floating absolute inset-0 -inset-y-8 rounded-3xl blur-3xl"
            style={{
              background:
                'linear-gradient(to bottom, rgba(36,97,255,0.12), rgba(124,58,237,0.06), transparent)',
            }}
          />

          <div className="relative bg-white rounded-2xl shadow-2xl shadow-slate-900/12 border border-slate-200/80 overflow-hidden floating">
            {/* Browser chrome */}
            <div className="flex items-center gap-2 px-4 py-3 bg-[#F5F6FA] border-b border-slate-200/80">
              <div className="w-3 h-3 rounded-full bg-red-400/80 hover:bg-red-400 transition-colors cursor-pointer" />
              <div className="w-3 h-3 rounded-full bg-amber-400/80 hover:bg-amber-400 transition-colors cursor-pointer" />
              <div className="w-3 h-3 rounded-full bg-green-400/80 hover:bg-green-400 transition-colors cursor-pointer" />
              <div className="flex-1 max-w-xs mx-4 bg-white rounded-full px-4 py-1 text-xs text-slate-400 border border-slate-200 font-mono">
                app.omnios.ai
              </div>
            </div>

            {/* Mock dashboard */}
            <div className="flex h-[360px] overflow-hidden">
              {/* Sidebar */}
              <div className="w-44 bg-[#0A1628] flex-shrink-0 flex flex-col">
                <div className="flex items-center gap-2 px-4 py-4 border-b border-white/10">
                  <div className="w-6 h-6 bg-gradient-to-br from-blue-400 to-violet-500 rounded-md flex items-center justify-center">
                    <Sparkles className="w-3 h-3 text-white" />
                  </div>
                  <span className="text-white text-sm font-bold" style={{ fontFamily: "'Ubuntu', sans-serif" }}>
                    OmniOS
                  </span>
                </div>
                <div className="flex-1 p-2 space-y-0.5">
                  {[
                    { label: 'Дашборд', active: true },
                    { label: 'Лиды' },
                    { label: 'Контакты' },
                    { label: 'Сообщения' },
                    { label: 'Настройки' },
                  ].map(item => (
                    <div
                      key={item.label}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs cursor-pointer transition-all duration-200 ${
                        item.active
                          ? 'bg-[#2461FF] text-white font-semibold shadow-lg shadow-blue-500/30'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                      }`}
                    >
                      <div
                        className={`w-1.5 h-1.5 rounded-full bg-current ${item.active ? 'active-dot' : 'opacity-60'}`}
                      />
                      {item.label}
                    </div>
                  ))}
                </div>
                <div className="m-2 p-2.5 rounded-xl bg-gradient-to-r from-[#2461FF]/20 to-[#7C3AED]/20 border border-white/10">
                  <div className="text-[9px] font-bold text-blue-300 mb-0.5 uppercase tracking-wider">ИИ-агент</div>
                  <div className="text-[8px] text-slate-400">3 задачи выполняются</div>
                </div>
              </div>

              {/* Main content */}
              <div className="flex-1 p-4 bg-slate-50 overflow-hidden">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <div className="text-sm font-bold text-slate-800" style={{ fontFamily: "'Ubuntu', sans-serif" }}>
                      Дашборд
                    </div>
                    <div className="text-[10px] text-slate-400">Вторник, 24 фев</div>
                  </div>
                  <div className="flex items-center gap-1.5 bg-emerald-50 text-emerald-700 text-[9px] font-bold px-2.5 py-1 rounded-full border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse inline-block" />
                    ИИ активен
                  </div>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {[
                    { label: 'Всего лидов', value: '247', trend: '+12%' },
                    { label: 'В воронке', value: '89', trend: '+5%' },
                    { label: 'Закрыто', value: '42', trend: '+18%' },
                    { label: 'Конверсия', value: '17%', trend: '+3%' },
                  ].map(stat => (
                    <div
                      key={stat.label}
                      className="bg-white rounded-xl p-2.5 border border-slate-200/60 shadow-sm hover:shadow-md transition-shadow"
                    >
                      <div className="text-[9px] text-slate-400 mb-1">{stat.label}</div>
                      <div className="text-base font-bold text-slate-900">{stat.value}</div>
                      <div className="text-[9px] text-emerald-600 font-medium">{stat.trend}</div>
                    </div>
                  ))}
                </div>

                {/* Bottom panels */}
                <div className="grid grid-cols-5 gap-2">
                  <div className="col-span-2 bg-white rounded-xl p-2.5 border border-slate-200/60 shadow-sm">
                    <div className="text-[9px] font-semibold text-slate-600 mb-2">Этапы воронки</div>
                    <div className="space-y-1.5">
                      {[
                        { label: 'Новые', pct: 75, color: '#2461FF' },
                        { label: 'Контакт', pct: 52, color: '#7C3AED' },
                        { label: 'Думают', pct: 35, color: '#06B6D4' },
                        { label: 'Сделка', pct: 20, color: '#10B981' },
                      ].map(s => (
                        <div key={s.label} className="flex items-center gap-1.5">
                          <div className="text-[8px] text-slate-400 w-16 shrink-0 truncate">{s.label}</div>
                          <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="h-1.5 rounded-full transition-all duration-1000"
                              style={{ width: `${s.pct}%`, backgroundColor: s.color }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="col-span-3 bg-white rounded-xl p-2.5 border border-slate-200/60 shadow-sm overflow-hidden">
                    <div className="flex items-center gap-1.5 mb-2">
                      <div className="w-3.5 h-3.5 rounded-md bg-gradient-to-br from-[#2461FF] to-[#7C3AED] flex items-center justify-center">
                        <span className="text-[6px] text-white font-bold">AI</span>
                      </div>
                      <div className="text-[9px] font-semibold text-slate-600">Активность ИИ-агента</div>
                    </div>
                    <div className="space-y-1.5">
                      {[
                        { icon: '🤖', text: 'Отправил follow-up Алие К. — этап Предложение', time: '2м' },
                        { icon: '📞', text: 'Разобрал звонок: Nomad Camp — 3 задачи', time: '8м' },
                        { icon: '🎯', text: 'Максат переведён на этап Переговоры', time: '15м' },
                        { icon: '💬', text: 'WhatsApp авто-ответ: Grand Hotel', time: '32м' },
                      ].map((a, i) => (
                        <div key={i} className="flex items-start gap-1.5">
                          <span className="text-[9px] mt-px shrink-0">{a.icon}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-[8.5px] text-slate-600 leading-tight truncate">{a.text}</div>
                          </div>
                          <div className="text-[8px] text-slate-300 shrink-0">{a.time}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// FEATURES
// ---------------------------------------------------------------------------

const FEATURES = [
  {
    Icon: Bot,
    colorFrom: 'from-blue-500',
    colorTo: 'to-blue-600',
    glow: 'shadow-blue-500/25',
    tag: 'ИИ-агент',
    title: 'Отвечает за вас',
    description:
      'ИИ-агент читает сообщения, отвечает на вопросы о ценах, номерах и услугах, и сам доводит клиента до бронирования. Без скриптов, без шаблонов.',
    bullets: ['Автоматическое продвижение по воронке', 'Отработка возражений', 'Цели и сценарии разговора'],
  },
  {
    Icon: BarChart3,
    colorFrom: 'from-violet-500',
    colorTo: 'to-violet-600',
    glow: 'shadow-violet-500/25',
    tag: 'Воронка',
    title: 'Видите всю воронку',
    description:
      'Все лиды на одном экране: кто только написал, кто уже думает, кто готов платить. Перетаскивайте карточки, меняйте статусы, не теряйте никого.',
    bullets: ['Kanban и таблица', 'Поиск и фильтры в реальном времени', 'Редактирование и групповые действия'],
  },
  {
    Icon: MessageSquare,
    colorFrom: 'from-cyan-500',
    colorTo: 'to-blue-500',
    glow: 'shadow-cyan-500/25',
    tag: 'Коммуникации',
    title: 'Пишет везде где удобно клиенту',
    description:
      'Telegram, WhatsApp, Instagram — в одном интерфейсе. Отправляйте фото, документы и ссылки прямо из CRM.',
    bullets: ['Telegram и WhatsApp', 'Instagram DM', 'SMS через RingCentral'],
  },
  {
    Icon: BookOpen,
    colorFrom: 'from-emerald-500',
    colorTo: 'to-teal-500',
    glow: 'shadow-emerald-500/25',
    tag: 'База знаний',
    title: 'Знает ваш продукт',
    description:
      'Загрузите прайс, фото, политики и FAQ. ИИ сам разберётся что, кому и когда отправить.',
    bullets: ['Загрузка прайсов и документов', 'Автоматическая отправка фото', 'Контекстные ответы на вопросы'],
  },
]

function Features() {
  const titleRef = useScrollReveal<HTMLDivElement>()
  const gridRef = useStaggerReveal<HTMLDivElement>(FEATURES.length)

  return (
    <section id="features" className="py-24 px-6">
      <div className="max-w-7xl mx-auto">
        <div ref={titleRef} className="scroll-reveal text-center mb-16">
          <div className="inline-flex items-center gap-1.5 bg-blue-50 text-blue-700 text-xs font-bold uppercase tracking-widest px-4 py-2 rounded-full border border-blue-200/60 mb-5">
            <Target className="w-3 h-3" />
            Возможности
          </div>
          <h2
            className="text-4xl md:text-5xl font-bold text-[#0A1628] tracking-tight mb-4"
            style={{ fontFamily: "'Ubuntu', sans-serif" }}
          >
            Всё что нужно команде,{' '}
            <span className="bg-gradient-to-r from-[#2461FF] to-[#7C3AED] bg-clip-text text-transparent">
              автоматически
            </span>
          </h2>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            От первого сообщения до закрытой сделки — OmniOS берёт рутину на себя, а команда занимается отношениями с клиентами.
          </p>
        </div>

        <div ref={gridRef} className="grid md:grid-cols-2 gap-6">
          {FEATURES.map((feat, i) => (
            <div
              key={feat.title}
              className="stagger-item scroll-reveal card-hover-lift bg-white rounded-2xl p-8 border border-slate-200/60 shadow-sm hover:border-blue-200/60 cursor-default"
            >
              <div className="flex items-start gap-4 mb-5">
                <div
                  className={`icon-bounce w-11 h-11 rounded-xl bg-gradient-to-br ${feat.colorFrom} ${feat.colorTo} flex items-center justify-center shadow-lg ${feat.glow} flex-shrink-0`}
                >
                  <feat.Icon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">{feat.tag}</div>
                  <h3
                    className="text-xl font-bold text-[#0A1628]"
                    style={{ fontFamily: "'Ubuntu', sans-serif" }}
                  >
                    {feat.title}
                  </h3>
                </div>
              </div>
              <p className="text-slate-500 text-sm leading-relaxed mb-5">{feat.description}</p>
              <ul className="space-y-2">
                {feat.bullets.map(bullet => (
                  <li key={bullet} className="flex items-center gap-2.5 text-sm text-slate-600">
                    <div className="w-4 h-4 rounded-full bg-gradient-to-br from-[#2461FF] to-[#7C3AED] flex items-center justify-center flex-shrink-0">
                      <Check className="w-2.5 h-2.5 text-white" />
                    </div>
                    {bullet}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// HOW IT WORKS
// ---------------------------------------------------------------------------

const STEPS = [
  {
    number: '01',
    Icon: Users,
    title: 'Добавьте лидов',
    description: 'Вручную или через интеграции. Укажите откуда пришёл клиент, что его интересует.',
  },
  {
    number: '02',
    Icon: Bot,
    title: 'ИИ берёт работу на себя',
    description:
      'Отвечает на сообщения, отправляет фото и прайсы, двигает лида по воронке, создаёт задачи для менеджеров.',
  },
  {
    number: '03',
    Icon: TrendingUp,
    title: 'Вы закрываете сделки',
    description: 'Менеджер подключается только когда клиент готов. Остальное — ИИ.',
  },
]

function HowItWorks() {
  const titleRef = useScrollReveal<HTMLDivElement>()
  const stepsRef = useStaggerReveal<HTMLDivElement>(STEPS.length)

  return (
    <section id="how-it-works" className="py-24 px-6 bg-gradient-to-b from-[#F0F4FF] to-[#F8FAFF]">
      <div className="max-w-6xl mx-auto">
        <div ref={titleRef} className="scroll-reveal text-center mb-16">
          <div className="inline-flex items-center gap-1.5 bg-violet-50 text-violet-700 text-xs font-bold uppercase tracking-widest px-4 py-2 rounded-full border border-violet-200/60 mb-5">
            <Activity className="w-3 h-3" />
            Как это работает
          </div>
          <h2
            className="text-4xl md:text-5xl font-bold text-[#0A1628] tracking-tight mb-4"
            style={{ fontFamily: "'Ubuntu', sans-serif" }}
          >
            Ваш полный цикл продаж
          </h2>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            Три простых шага от первого контакта до постоянного клиента — полностью автоматически.
          </p>
        </div>

        <div ref={stepsRef} className="grid md:grid-cols-3 gap-6 relative">
          {/* SVG animated connector */}
          <div className="hidden md:block absolute top-[52px] left-[calc(16.66%+24px)] right-[calc(16.66%+24px)] h-6 overflow-visible pointer-events-none">
            <svg width="100%" height="24" viewBox="0 0 100% 24" preserveAspectRatio="none">
              <line
                x1="0"
                y1="12"
                x2="100%"
                y2="12"
                stroke="url(#connectorGrad)"
                strokeWidth="1.5"
                className="animated-dash"
              />
              <defs>
                <linearGradient id="connectorGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#2461FF" stopOpacity="0.4" />
                  <stop offset="50%" stopColor="#7C3AED" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="#2461FF" stopOpacity="0.4" />
                </linearGradient>
              </defs>
            </svg>
          </div>

          {STEPS.map((step, i) => (
            <div
              key={step.number}
              className="stagger-item scroll-reveal card-hover-lift relative bg-white rounded-2xl p-7 border border-slate-200/60 shadow-sm text-center"
            >
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-[#2461FF] to-[#7C3AED] text-white text-xs font-bold px-3 py-1 rounded-full shadow-lg shadow-blue-500/25">
                {step.number}
              </div>
              <div className="icon-bounce w-12 h-12 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-blue-50 to-violet-50 border border-slate-200/60 flex items-center justify-center">
                <step.Icon className="w-6 h-6 text-[#2461FF]" />
              </div>
              <h3
                className="text-lg font-bold text-[#0A1628] mb-3"
                style={{ fontFamily: "'Ubuntu', sans-serif" }}
              >
                {step.title}
              </h3>
              <p className="text-sm text-slate-500 leading-relaxed">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// INDUSTRIES
// ---------------------------------------------------------------------------

const INDUSTRIES = [
  {
    Icon: Building2,
    iconGrad: 'from-[#2461FF] to-[#5B8EFF]',
    iconShadow: 'shadow-blue-500/30',
    bg: 'from-[#0A1628] to-[#132344]',
    blobColor: 'rgba(36,97,255,0.35)',
    accentColor: 'text-blue-300',
    bulletBg: 'bg-[#2461FF]/30',
    bulletBorder: 'border-[#2461FF]/50',
    bulletIcon: 'text-blue-300',
    labelColor: 'text-blue-300',
    subLabel: 'Больше броней, меньше звонков',
    subLabelColor: 'text-blue-200',
    title: 'Отели и гостиницы',
    desc: 'Гости пишут в Telegram — ИИ отвечает на вопросы о номерах, ценах и питании, отправляет фото и закрывает бронирование. Менеджер получает уже готового клиента.',
    bullets: [
      'Гости пишут в Telegram — ИИ отвечает на вопросы о номерах, ценах и питании',
      'Отправляет фото и закрывает бронирование без участия менеджера',
      'Менеджер получает уже готового клиента',
      'Мультиобъектная воронка в одном интерфейсе',
    ],
    stat: 'до 80%',
    statLabel: 'запросов обрабатывает ИИ',
  },
  {
    Icon: Dumbbell,
    iconGrad: 'from-[#7C3AED] to-[#A855F7]',
    iconShadow: 'shadow-violet-500/30',
    bg: 'from-[#1A0A28] to-[#2A1044]',
    blobColor: 'rgba(124,58,237,0.35)',
    accentColor: 'text-violet-300',
    bulletBg: 'bg-[#7C3AED]/30',
    bulletBorder: 'border-[#7C3AED]/50',
    bulletIcon: 'text-violet-300',
    labelColor: 'text-violet-300',
    subLabel: 'Записывайте клиентов без администратора',
    subLabelColor: 'text-violet-200',
    title: 'Фитнес-центры',
    desc: 'Новый клиент написал в Instagram? ИИ расскажет про абонементы, ответит на вопросы и напомнит о пробном занятии. Вы получаете запись — не переписку.',
    bullets: [
      'Новый клиент написал в Instagram? ИИ расскажет про абонементы',
      'Ответит на вопросы и напомнит о пробном занятии',
      'Вы получаете запись — не переписку',
      'Автоматические напоминания о продлении абонемента',
    ],
    stat: 'в 3 раза',
    statLabel: 'быстрее обработка заявок',
  },
  {
    Icon: ShoppingCart,
    iconGrad: 'from-emerald-500 to-teal-500',
    iconShadow: 'shadow-emerald-500/30',
    bg: 'from-[#0A1F1A] to-[#0D2E26]',
    blobColor: 'rgba(16,185,129,0.30)',
    accentColor: 'text-emerald-300',
    bulletBg: 'bg-emerald-500/30',
    bulletBorder: 'border-emerald-500/50',
    bulletIcon: 'text-emerald-300',
    labelColor: 'text-emerald-300',
    subLabel: 'Возвращайте клиентов и увеличивайте повторные продажи',
    subLabelColor: 'text-emerald-200',
    title: 'Интернет-магазины',
    desc: 'ИИ следит за лидами, напоминает о брошенных корзинах, отвечает на вопросы о доставке и помогает с выбором товара — прямо в мессенджере клиента.',
    bullets: [
      'ИИ следит за лидами и напоминает о брошенных корзинах',
      'Отвечает на вопросы о доставке и помогает с выбором товара',
      'Прямо в мессенджере клиента — без звонков',
      'Автоматические follow-up для повторных покупок',
    ],
    stat: '+40%',
    statLabel: 'к повторным покупкам',
  },
]

function Industries() {
  const titleRef = useScrollReveal<HTMLDivElement>()
  const gridRef = useStaggerReveal<HTMLDivElement>(INDUSTRIES.length)

  return (
    <section id="industries" className="py-24 px-6">
      <div className="max-w-7xl mx-auto">
        <div ref={titleRef} className="scroll-reveal text-center mb-16">
          <div className="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 text-xs font-bold uppercase tracking-widest px-4 py-2 rounded-full border border-emerald-200/60 mb-5">
            <Globe className="w-3 h-3" />
            Для каких отраслей
          </div>
          <h2
            className="text-4xl md:text-5xl font-bold text-[#0A1628] tracking-tight mb-4"
            style={{ fontFamily: "'Ubuntu', sans-serif" }}
          >
            Создан для вашей отрасли
          </h2>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            OmniOS разработан для бизнесов, где доход строится на отношениях с клиентами.
          </p>
        </div>

        <div ref={gridRef} className="grid md:grid-cols-3 gap-8">
          {INDUSTRIES.map(ind => (
            <div
              key={ind.title}
              className={`industry-card stagger-item scroll-reveal relative overflow-hidden bg-gradient-to-br ${ind.bg} rounded-2xl p-8 text-white border border-white/10 card-hover-lift cursor-default`}
            >
              <div
                aria-hidden="true"
                className="inner-blob absolute -top-16 -right-16 w-52 h-52 rounded-full blur-3xl"
                style={{ background: `radial-gradient(circle, ${ind.blobColor} 0%, transparent 70%)` }}
              />
              <div className="relative z-10">
                <div
                  className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${ind.iconGrad} flex items-center justify-center mb-6 shadow-lg ${ind.iconShadow} transition-transform duration-300 group-hover:scale-110`}
                >
                  <ind.Icon className="w-7 h-7 text-white" />
                </div>
                <div className={`text-xs font-bold ${ind.labelColor} uppercase tracking-widest mb-2`}>Отрасль</div>
                <h3 className="text-2xl font-bold mb-2" style={{ fontFamily: "'Ubuntu', sans-serif" }}>
                  {ind.title}
                </h3>
                <p className={`${ind.subLabelColor} text-sm font-medium mb-4`}>{ind.subLabel}</p>
                <p className="text-slate-300 text-sm leading-relaxed mb-6">{ind.desc}</p>
                <ul className="space-y-3">
                  {ind.bullets.map(item => (
                    <li key={item} className="flex items-start gap-3 text-sm text-slate-200">
                      <div
                        className={`w-5 h-5 rounded-full ${ind.bulletBg} border ${ind.bulletBorder} flex items-center justify-center flex-shrink-0 mt-0.5`}
                      >
                        <Check className={`w-3 h-3 ${ind.bulletIcon}`} />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
                <div className="mt-8 pt-6 border-t border-white/10 text-center">
                  <div className="text-2xl font-bold text-white" style={{ fontFamily: "'Ubuntu', sans-serif" }}>
                    {ind.stat}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{ind.statLabel}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// AI AGENT SPOTLIGHT
// ---------------------------------------------------------------------------

const AUTONOMY_FEATURES = [
  {
    Icon: Target,
    title: 'Сам двигает сделки',
    description: 'Анализирует переписку и переводит лида на следующий этап воронки когда видит интерес.',
  },
  {
    Icon: Shield,
    title: 'Отрабатывает возражения',
    description: 'Цена высокая? Надо подумать? ИИ знает как ответить, используя ваши материалы.',
  },
  {
    Icon: TrendingUp,
    title: 'Создаёт задачи',
    description: 'После каждого касания ИИ создаёт задачи для менеджеров: позвонить, уточнить, отправить КП.',
  },
  {
    Icon: Zap,
    title: 'Не забывает никого',
    description: 'Сам пишет лидам которые замолчали, по расписанию, без напоминаний.',
  },
]

// CountUp stat component
function StatCounter({ value, label }: { value: string; label: string }) {
  // Extract numeric part for animation
  const numMatch = value.match(/[\d.]+/)
  const num = numMatch ? parseFloat(numMatch[0]) : 0
  const prefix = value.startsWith('+') ? '+' : value.startsWith('до') ? 'до ' : value.startsWith('в') ? 'в ' : ''
  const suffix = value.endsWith('%') ? '%' : value.endsWith('раза') ? ' раза' : value === '24/7' ? '' : ''
  const isSpecial = value === '24/7'

  const { ref, value: count } = useCountUp(num, 1600)

  if (isSpecial) {
    return (
      <div>
        <div ref={ref} className="text-3xl font-bold text-white mb-1" style={{ fontFamily: "'Ubuntu', sans-serif" }}>
          24/7
        </div>
        <div className="text-sm text-slate-400">{label}</div>
      </div>
    )
  }

  return (
    <div>
      <div ref={ref} className="text-3xl font-bold text-white mb-1" style={{ fontFamily: "'Ubuntu', sans-serif" }}>
        {prefix}{count}{suffix}
      </div>
      <div className="text-sm text-slate-400">{label}</div>
    </div>
  )
}

function AIAgentSpotlight() {
  const titleRef = useScrollReveal<HTMLDivElement>()
  const cardsRef = useStaggerReveal<HTMLDivElement>(AUTONOMY_FEATURES.length)
  const statsRef = useScrollReveal<HTMLDivElement>()

  return (
    <section id="ai-agent" className="py-24 px-6 bg-[#0A1628] relative overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] rounded-full blob-anim-1"
          style={{ background: 'radial-gradient(ellipse, rgba(36,97,255,0.18) 0%, transparent 70%)' }}
        />
        <div
          className="absolute bottom-0 right-0 w-[500px] h-[300px] rounded-full blob-anim-2"
          style={{ background: 'radial-gradient(ellipse, rgba(124,58,237,0.15) 0%, transparent 70%)' }}
        />
      </div>

      <div className="max-w-6xl mx-auto relative z-10">
        <div ref={titleRef} className="scroll-reveal text-center mb-16">
          <div className="inline-flex items-center gap-1.5 bg-[#2461FF]/20 text-blue-300 text-xs font-bold uppercase tracking-widest px-4 py-2 rounded-full border border-[#2461FF]/30 mb-5">
            <Bot className="w-3 h-3" />
            ИИ-агент
          </div>
          <h2
            className="text-4xl md:text-5xl font-bold text-white tracking-tight mb-4"
            style={{ fontFamily: "'Ubuntu', sans-serif" }}
          >
            Что делает{' '}
            <span className="bg-gradient-to-r from-[#5B8EFF] to-[#A78BFA] bg-clip-text text-transparent">
              ИИ-агент
            </span>
          </h2>
          <p className="text-lg text-slate-400 max-w-xl mx-auto">
            OmniOS не отправляет шаблонные сообщения — он понимает контекст, определяет намерение и действует чтобы двигать сделки вперёд.
          </p>
        </div>

        <div ref={cardsRef} className="grid md:grid-cols-2 lg:grid-cols-4 gap-5 mb-12">
          {AUTONOMY_FEATURES.map(feat => (
            <div
              key={feat.title}
              className="stagger-item scroll-reveal card-hover-lift bg-white/[0.04] backdrop-blur-sm rounded-2xl p-6 border border-white/10 hover:bg-white/[0.08] hover:border-white/20 cursor-default"
            >
              <div className="glow-pulse icon-bounce w-10 h-10 rounded-xl bg-gradient-to-br from-[#2461FF]/30 to-[#7C3AED]/30 border border-white/10 flex items-center justify-center mb-4">
                <feat.Icon className="w-5 h-5 text-blue-300" />
              </div>
              <h3
                className="text-base font-bold text-white mb-2"
                style={{ fontFamily: "'Ubuntu', sans-serif" }}
              >
                {feat.title}
              </h3>
              <p className="text-sm text-slate-400 leading-relaxed">{feat.description}</p>
            </div>
          ))}
        </div>

        {/* Stats banner with count-up */}
        <div
          ref={statsRef as React.Ref<HTMLDivElement>}
          className="scroll-reveal bg-gradient-to-r from-[#2461FF]/20 to-[#7C3AED]/20 rounded-2xl p-8 border border-white/10"
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
            <StatCounter value="24/7" label="работает без выходных" />
            <StatCounter value="до 80%" label="запросов без менеджера" />
            <StatCounter value="в 3 раза" label="быстрее обработка заявок" />
          </div>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// CTA SECTION
// ---------------------------------------------------------------------------

function CTASection() {
  const ref = useScrollReveal<HTMLDivElement>()

  return (
    <section className="py-24 px-6 bg-[#F8FAFF] relative overflow-hidden">
      {/* Animated gradient bg */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 animated-gradient-bg"
        style={{
          background:
            'linear-gradient(135deg, rgba(36,97,255,0.06) 0%, rgba(124,58,237,0.08) 50%, rgba(36,97,255,0.04) 100%)',
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] rounded-full blob-anim-1"
        style={{ background: 'radial-gradient(ellipse, rgba(36,97,255,0.10) 0%, transparent 70%)' }}
      />

      <div ref={ref} className="scroll-reveal max-w-3xl mx-auto text-center relative z-10">
        <div className="inline-flex items-center gap-1.5 bg-gradient-to-r from-blue-50 to-violet-50 text-blue-700 text-xs font-bold uppercase tracking-widest px-4 py-2 rounded-full border border-blue-200/60 mb-8">
          <Sparkles className="w-3 h-3 fill-current" />
          Начните сегодня
        </div>
        <h2
          className="text-4xl md:text-5xl font-bold text-[#0A1628] tracking-tight mb-6"
          style={{ fontFamily: "'Ubuntu', sans-serif" }}
        >
          Готовы перестать{' '}
          <span className="bg-gradient-to-r from-[#2461FF] to-[#7C3AED] bg-clip-text text-transparent">
            терять лидов?
          </span>
        </h2>
        <p className="text-lg text-slate-500 mb-10">
          Подключите OmniOS и ваш ИИ-агент начнёт работать уже сегодня
        </p>
        <div className="flex items-center justify-center gap-4 flex-wrap mb-4">
          <Link to="/register">
            <Button
              size="lg"
              className="shimmer-btn h-14 px-10 text-base font-semibold bg-gradient-to-r from-[#2461FF] to-[#7C3AED] hover:opacity-95 text-white border-0 shadow-2xl shadow-blue-500/25 transition-all duration-300 hover:scale-105 hover:shadow-blue-500/40 group"
            >
              Начать бесплатно
              <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Button>
          </Link>
          <Link to="/login">
            <Button
              variant="outline"
              size="lg"
              className="h-14 px-10 text-base font-medium border-slate-200 bg-white/70 hover:bg-white text-slate-700 transition-all duration-300 hover:scale-105 hover:shadow-lg"
            >
              Войти
            </Button>
          </Link>
        </div>
        <p className="text-sm text-slate-400">Бесплатно · Без кредитной карты · Быстрая настройка</p>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// FOOTER
// ---------------------------------------------------------------------------

function Footer() {
  const ref = useScrollReveal<HTMLElement>()
  const links = [
    { label: 'Возможности', href: '#features' },
    { label: 'Как это работает', href: '#how-it-works' },
    { label: 'Отрасли', href: '#industries' },
    { label: 'Войти', href: '/login' },
  ]
  return (
    <footer ref={ref} className="scroll-reveal bg-[#0A1628] py-12 px-6 border-t border-white/10">
      <div className="footer-divider mb-8 opacity-60" />
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex flex-col items-center md:items-start gap-1">
          <div className="flex items-center gap-2.5 group">
            <div className="w-7 h-7 bg-gradient-to-br from-[#2461FF] to-[#7C3AED] rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
              <Sparkles className="w-3.5 h-3.5 text-white" />
            </div>
            <span
              className="text-white font-bold text-lg"
              style={{ fontFamily: "'Ubuntu', sans-serif" }}
            >
              OmniOS
            </span>
          </div>
          <p className="text-slate-500 text-xs mt-1">CRM, которая работает пока вы спите</p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-6">
          {links.map(link => (
            <a
              key={link.label}
              href={link.href}
              className="text-sm text-slate-500 hover:text-slate-300 transition-colors relative after:absolute after:bottom-0 after:left-0 after:h-px after:w-0 after:bg-slate-300 after:transition-all after:duration-300 hover:after:w-full pb-0.5"
            >
              {link.label}
            </a>
          ))}
        </div>
        <p className="text-slate-500 text-sm">© 2025 OmniOS. Все права защищены.</p>
      </div>

      {/* Developed by Axon */}
      <div className="footer-divider mt-8 mb-6 opacity-30" />
      <div className="max-w-6xl mx-auto flex items-center justify-center gap-2">
        <span className="text-slate-600 text-xs">Разработано командой</span>
        <span className="inline-flex items-center gap-1.5 bg-gradient-to-r from-[#2461FF]/20 to-[#7C3AED]/20 border border-white/10 text-white text-xs font-bold px-3 py-1 rounded-full tracking-wide hover:from-[#2461FF]/30 hover:to-[#7C3AED]/30 transition-all duration-300 cursor-default">
          <span className="w-1.5 h-1.5 rounded-full bg-gradient-to-r from-[#2461FF] to-[#7C3AED] inline-block" />
          Axon
        </span>
      </div>
    </footer>
  )
}
