import { createFileRoute, Link, Navigate } from '@tanstack/react-router'
import { useAuth } from '@/contexts/auth-context'
import {
  ArrowRight,
  Bot,
  Users,
  MessageSquare,
  BookOpen,
  Check,
  Target,
  Shield,
  ClipboardList,
  Zap,
  LayoutDashboard,
  GitBranch,
  Hotel,
  Settings,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useEffect, useRef } from 'react'

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
            setTimeout(() => item.classList.add('is-visible'), i * 90)
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
      className="bg-white text-slate-900 overflow-x-hidden"
      style={{ fontFamily: "'Inter', system-ui, sans-serif", colorScheme: 'light' }}
    >
      <Navbar />
      <Hero />
      <Features />
      <HowItWorks />
      <ForHotels />
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
      className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-sm border-b border-slate-200 transition-shadow duration-200"
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <a href="#" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-gradient-to-br from-[#2461FF] to-[#7C3AED] rounded-md flex items-center justify-center">
              <Hotel className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-lg text-slate-900">OmniOS</span>
          </a>
          <div className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-500">
            {[
              { label: 'Возможности', href: '#features' },
              { label: 'Как это работает', href: '#how-it-works' },
              { label: 'Для отеля', href: '#for-hotels' },
              { label: 'ИИ-агент', href: '#ai-agent' },
            ].map(({ label, href }) => (
              <a key={href} href={href} className="hover:text-slate-900 transition-colors">
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
            <Button size="sm" className="bg-gradient-to-r from-[#2461FF] to-[#7C3AED] hover:opacity-90 text-white font-semibold border-0">
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
    <section className="relative pt-28 pb-16">
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex justify-center mb-6">
          <div
            ref={badgeRef as React.Ref<HTMLDivElement>}
            className="scroll-reveal inline-flex items-center gap-1.5 bg-blue-50 text-blue-700 text-xs font-semibold px-3 py-1.5 rounded-full border border-blue-200/60"
          >
            Для отельного бизнеса
          </div>
        </div>

        <h1
          ref={h1Ref}
          className="scroll-reveal delay-100 text-center text-4xl md:text-5xl lg:text-6xl font-bold text-slate-900 leading-tight tracking-tight mb-6 max-w-3xl mx-auto"
        >
          CRM для отелей, где гостям отвечает{' '}
          <span className="bg-gradient-to-r from-[#2461FF] to-[#7C3AED] bg-clip-text text-transparent">ИИ</span>
        </h1>

        <p
          ref={subRef as React.Ref<HTMLParagraphElement>}
          className="scroll-reveal delay-200 text-center text-lg text-slate-500 max-w-xl mx-auto mb-10 leading-relaxed"
        >
          ИИ-агент ведёт переписку в Telegram, WhatsApp и Instagram: отвечает про
          номера и цены, считает стоимость по вашим тарифам и доводит гостя до
          брони. Менеджер подключается, когда осталось только подтвердить.
        </p>

        <div
          ref={ctaRef as React.Ref<HTMLDivElement>}
          className="scroll-reveal delay-300 flex items-center justify-center gap-3 flex-wrap mb-16"
        >
          <Link to="/register">
            <Button size="lg" className="h-11 px-7 bg-gradient-to-r from-[#2461FF] to-[#7C3AED] hover:opacity-90 text-white font-semibold border-0 shadow-lg shadow-blue-500/20 group">
              Начать бесплатно
              <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Button>
          </Link>
          <Link to="/login">
            <Button variant="outline" size="lg" className="h-11 px-7 font-medium border-slate-300">
              Войти
            </Button>
          </Link>
        </div>

        {/* Dashboard mockup, styled like the actual product UI */}
        <div ref={mockupRef as React.Ref<HTMLDivElement>} className="scroll-reveal scale delay-400 max-w-4xl mx-auto">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-200">
              <div className="w-2.5 h-2.5 rounded-full bg-slate-300" />
              <div className="w-2.5 h-2.5 rounded-full bg-slate-300" />
              <div className="w-2.5 h-2.5 rounded-full bg-slate-300" />
              <div className="flex-1 max-w-xs mx-4 bg-white rounded-md px-3 py-1 text-xs text-slate-400 border border-slate-200 font-mono">
                app.omnios.ai/dashboard
              </div>
            </div>

            <div className="flex h-[340px] overflow-hidden">
              {/* Sidebar */}
              <div className="w-40 bg-slate-900 flex-shrink-0 flex flex-col">
                <div className="flex items-center gap-2 px-3 py-3 border-b border-white/10">
                  <div className="w-5 h-5 bg-white/10 rounded flex items-center justify-center">
                    <Hotel className="w-3 h-3 text-white" />
                  </div>
                  <span className="text-white text-xs font-bold">OmniOS</span>
                </div>
                <div className="flex-1 p-1.5 space-y-0.5">
                  {[
                    { label: 'Дашборд', Icon: LayoutDashboard, active: true },
                    { label: 'Лиды', Icon: Users },
                    { label: 'Сообщения', Icon: MessageSquare },
                    { label: 'ИИ-Флоу', Icon: GitBranch },
                    { label: 'Данные отеля', Icon: Hotel },
                    { label: 'Настройки', Icon: Settings },
                  ].map(item => (
                    <div
                      key={item.label}
                      className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[11px] ${
                        item.active ? 'bg-[#2461FF] text-white font-medium' : 'text-slate-400'
                      }`}
                    >
                      <item.Icon className="w-3 h-3 shrink-0" />
                      {item.label}
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-2 px-3 py-3 border-t border-white/10">
                  <div className="w-5 h-5 rounded bg-slate-700 flex items-center justify-center text-[9px] text-white font-semibold">
                    А
                  </div>
                  <div className="min-w-0">
                    <div className="text-[10px] text-white truncate">Айгуль С.</div>
                    <div className="text-[8px] text-slate-500 truncate">Grand Hotel</div>
                  </div>
                </div>
              </div>

              {/* Main content */}
              <div className="flex-1 p-4 bg-slate-50 overflow-hidden">
                <div className="mb-3">
                  <div className="text-sm font-bold text-slate-800">Дашборд</div>
                  <div className="text-[10px] text-slate-400">Обзор лидов и броней</div>
                </div>

                {/* Stat cards — matches the real dashboard's stat cards */}
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {[
                    { label: 'Всего лидов', value: '128', border: 'border-l-blue-500' },
                    { label: 'Финальный этап', value: '34', border: 'border-l-emerald-500' },
                    { label: 'Конверсия', value: '27%', border: 'border-l-violet-500' },
                    { label: 'В воронке', value: '94', border: 'border-l-orange-500' },
                  ].map(stat => (
                    <div
                      key={stat.label}
                      className={`bg-white rounded-md p-2 border border-slate-200 border-l-[3px] ${stat.border}`}
                    >
                      <div className="text-[8px] text-slate-400 mb-1">{stat.label}</div>
                      <div className="text-sm font-bold text-slate-900">{stat.value}</div>
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-5 gap-2">
                  <div className="col-span-2 bg-white rounded-md p-2.5 border border-slate-200">
                    <div className="text-[9px] font-semibold text-slate-600 mb-2">Воронка</div>
                    <div className="space-y-1.5">
                      {[
                        { label: 'Новые', pct: 70, color: '#3b82f6' },
                        { label: 'В переписке', pct: 48, color: '#8b5cf6' },
                        { label: 'Ждут оплату', pct: 30, color: '#f59e0b' },
                        { label: 'Бронь подтверждена', pct: 22, color: '#10b981' },
                      ].map(s => (
                        <div key={s.label} className="flex items-center gap-1.5">
                          <div className="text-[7.5px] text-slate-400 w-14 shrink-0 truncate">{s.label}</div>
                          <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div className="h-1.5 rounded-full" style={{ width: `${s.pct}%`, backgroundColor: s.color }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="col-span-3 bg-white rounded-md p-2.5 border border-slate-200">
                    <div className="text-[9px] font-semibold text-slate-600 mb-2">Недавние лиды</div>
                    <div className="space-y-1.5">
                      {[
                        { name: 'Алия К.', stage: 'Предложение', time: '2 мин' },
                        { name: 'Максат Е.', stage: 'Переговоры', time: '18 мин' },
                        { name: 'Динара С.', stage: 'Новый', time: '1 ч' },
                        { name: 'Nomad Camp', stage: 'Бронь подтверждена', time: '3 ч' },
                      ].map(lead => (
                        <div key={lead.name} className="flex items-center justify-between">
                          <span className="text-[8.5px] text-slate-700 truncate">{lead.name}</span>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <span className="text-[7.5px] text-slate-500 border border-slate-200 rounded px-1 py-0.5">
                              {lead.stage}
                            </span>
                            <span className="text-[7.5px] text-slate-300">{lead.time}</span>
                          </div>
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
    iconBg: 'bg-blue-50',
    iconColor: 'text-blue-600',
    tag: 'ИИ-агент',
    title: 'Отвечает вместо менеджера',
    description:
      'Читает сообщение гостя, понимает вопрос и отвечает: про номера, цены, заезд и выезд, услуги. Считает стоимость по вашим тарифам и предлагает бронь.',
    bullets: ['Ведёт диалог до брони', 'Отрабатывает возражения по цене', 'Передаёт менеджеру, когда нужно подтверждение'],
  },
  {
    Icon: Users,
    iconBg: 'bg-violet-50',
    iconColor: 'text-violet-600',
    tag: 'Воронка',
    title: 'Все лиды на одном экране',
    description:
      'Канбан и таблица лидов с этапами, поиском и фильтрами. Видно, кто только написал, кто думает, а кто готов платить.',
    bullets: ['Kanban и таблица', 'Поиск и фильтры', 'Заметки и задачи по каждому лиду'],
  },
  {
    Icon: MessageSquare,
    iconBg: 'bg-cyan-50',
    iconColor: 'text-cyan-600',
    tag: 'Каналы',
    title: 'Пишет там, где удобно гостю',
    description:
      'Telegram, WhatsApp, Instagram Direct и SMS — в одном интерфейсе, без переключения между приложениями.',
    bullets: ['Telegram и WhatsApp', 'Instagram Direct', 'SMS через RingCentral'],
  },
  {
    Icon: BookOpen,
    iconBg: 'bg-emerald-50',
    iconColor: 'text-emerald-600',
    tag: 'База знаний',
    title: 'Знает ваш отель',
    description:
      'Загрузите тарифы на номера, политики отмены, фото и FAQ — ИИ сам разберётся, что ответить и когда прислать фото номера.',
    bullets: ['Тарифы и наличие номеров', 'Политики и FAQ', 'Фото номеров и услуг'],
  },
]

function Features() {
  const titleRef = useScrollReveal<HTMLDivElement>()
  const gridRef = useStaggerReveal<HTMLDivElement>(FEATURES.length)

  return (
    <section id="features" className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <div ref={titleRef} className="scroll-reveal text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight mb-3">Что делает CRM</h2>
          <p className="text-slate-500 max-w-lg mx-auto">
            От первого сообщения до подтверждённой брони — команда занимается гостями, а не перепиской.
          </p>
        </div>

        <div ref={gridRef} className="grid md:grid-cols-2 gap-5">
          {FEATURES.map(feat => (
            <div
              key={feat.title}
              className="stagger-item scroll-reveal bg-white rounded-xl p-7 border border-slate-200 hover:border-slate-300 transition-colors"
            >
              <div className="flex items-start gap-3 mb-4">
                <div className={`w-9 h-9 rounded-lg ${feat.iconBg} flex items-center justify-center flex-shrink-0`}>
                  <feat.Icon className={`w-4.5 h-4.5 ${feat.iconColor}`} />
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-0.5">{feat.tag}</div>
                  <h3 className="text-lg font-bold text-slate-900">{feat.title}</h3>
                </div>
              </div>
              <p className="text-slate-500 text-sm leading-relaxed mb-4">{feat.description}</p>
              <ul className="space-y-1.5">
                {feat.bullets.map(bullet => (
                  <li key={bullet} className="flex items-center gap-2 text-sm text-slate-600">
                    <Check className={`w-3.5 h-3.5 ${feat.iconColor} flex-shrink-0`} />
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
    Icon: Hotel,
    title: 'Добавьте отель',
    description: 'Тарифы на номера, наличие, политики отмены и FAQ. Занимает один вечер.',
  },
  {
    number: '02',
    Icon: MessageSquare,
    title: 'Подключите каналы',
    description: 'Telegram, WhatsApp или Instagram — там, где гости пишут вам сейчас.',
  },
  {
    number: '03',
    Icon: Bot,
    title: 'ИИ ведёт переписку',
    description: 'Отвечает, считает цену, доводит до брони. Менеджер подключается для подтверждения.',
  },
]

function HowItWorks() {
  const titleRef = useScrollReveal<HTMLDivElement>()
  const stepsRef = useStaggerReveal<HTMLDivElement>(STEPS.length)

  return (
    <section id="how-it-works" className="py-20 px-6 bg-slate-50">
      <div className="max-w-5xl mx-auto">
        <div ref={titleRef} className="scroll-reveal text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight mb-3">Как это работает</h2>
          <p className="text-slate-500 max-w-lg mx-auto">Три шага от первого сообщения гостя до подтверждённой брони.</p>
        </div>

        <div ref={stepsRef} className="grid md:grid-cols-3 gap-5">
          {STEPS.map(step => (
            <div key={step.number} className="stagger-item scroll-reveal bg-white rounded-xl p-6 border border-slate-200">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-50 to-violet-50 flex items-center justify-center">
                  <step.Icon className="w-4.5 h-4.5 text-[#2461FF]" />
                </div>
                <span className="text-xs font-bold text-[#7C3AED]">{step.number}</span>
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-2">{step.title}</h3>
              <p className="text-sm text-slate-500 leading-relaxed">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// FOR HOTELS
// ---------------------------------------------------------------------------

const HOTEL_BULLETS = [
  'Тарифы, наличие номеров и политики отмены — в одном месте',
  'Диалог в Telegram, WhatsApp и Instagram без переключения между приложениями',
  'Задачи менеджеру создаются автоматически: позвонить, уточнить, отправить документы',
  'История переписки и брони видна всей команде',
]

function ForHotels() {
  const ref = useScrollReveal<HTMLDivElement>()

  return (
    <section id="for-hotels" className="py-20 px-6">
      <div ref={ref} className="scroll-reveal max-w-4xl mx-auto bg-slate-900 rounded-2xl p-10 text-white relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 -right-24 w-72 h-72 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(36,97,255,0.25) 0%, transparent 70%)' }}
        />
        <div className="relative">
          <div className="text-xs font-semibold text-blue-300 uppercase tracking-wide mb-3">Отельный бизнес</div>
          <h2 className="text-2xl md:text-3xl font-bold mb-4">Одна CRM для гостей, броней и переписки</h2>
          <p className="text-slate-300 leading-relaxed mb-6 max-w-2xl">
            Гость пишет в Telegram или Instagram с вопросом о номере — ИИ отвечает по вашим тарифам и политикам,
            отправляет фото и доводит до подтверждённой брони. Менеджер видит уже готового клиента и всю переписку в
            одном месте.
          </p>
          <ul className="space-y-2.5">
            {HOTEL_BULLETS.map(item => (
              <li key={item} className="flex items-start gap-2.5 text-sm text-slate-200">
                <Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                {item}
              </li>
            ))}
          </ul>
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
    iconBg: 'bg-blue-50',
    iconColor: 'text-blue-600',
    title: 'Двигает лида по воронке',
    description: 'Видит, что гость готов, и сам переводит его на следующий этап.',
  },
  {
    Icon: Shield,
    iconBg: 'bg-violet-50',
    iconColor: 'text-violet-600',
    title: 'Отрабатывает возражения',
    description: 'Цена высокая? Нужно подумать? Отвечает, опираясь на ваши тарифы и FAQ.',
  },
  {
    Icon: ClipboardList,
    iconBg: 'bg-cyan-50',
    iconColor: 'text-cyan-600',
    title: 'Ставит задачи менеджеру',
    description: 'После каждого диалога создаёт задачу: позвонить, уточнить детали, отправить документы.',
  },
  {
    Icon: Zap,
    iconBg: 'bg-emerald-50',
    iconColor: 'text-emerald-600',
    title: 'Пишет первым, если гость замолчал',
    description: 'Follow-up по расписанию, без напоминаний с вашей стороны.',
  },
]

function AIAgentSpotlight() {
  const titleRef = useScrollReveal<HTMLDivElement>()
  const cardsRef = useStaggerReveal<HTMLDivElement>(AUTONOMY_FEATURES.length)

  return (
    <section id="ai-agent" className="py-20 px-6 bg-slate-50">
      <div className="max-w-5xl mx-auto">
        <div ref={titleRef} className="scroll-reveal text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight mb-3">Что делает ИИ-агент</h2>
          <p className="text-slate-500 max-w-lg mx-auto">
            Не шаблонные ответы: агент понимает контекст диалога и действует, чтобы довести гостя до брони.
          </p>
        </div>

        <div ref={cardsRef} className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {AUTONOMY_FEATURES.map(feat => (
            <div key={feat.title} className="stagger-item scroll-reveal bg-white rounded-xl p-5 border border-slate-200">
              <div className={`w-8 h-8 rounded-lg ${feat.iconBg} flex items-center justify-center mb-3`}>
                <feat.Icon className={`w-4 h-4 ${feat.iconColor}`} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-1.5">{feat.title}</h3>
              <p className="text-sm text-slate-500 leading-relaxed">{feat.description}</p>
            </div>
          ))}
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
    <section className="py-20 px-6">
      <div ref={ref} className="scroll-reveal max-w-2xl mx-auto text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight mb-4">Готовы попробовать?</h2>
        <p className="text-lg text-slate-500 mb-8">Подключите Telegram или WhatsApp — и ИИ-агент начнёт отвечать гостям.</p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Link to="/register">
            <Button size="lg" className="h-12 px-8 bg-gradient-to-r from-[#2461FF] to-[#7C3AED] hover:opacity-90 text-white font-semibold border-0 shadow-lg shadow-blue-500/20 group">
              Начать бесплатно
              <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Button>
          </Link>
          <Link to="/login">
            <Button variant="outline" size="lg" className="h-12 px-8 font-medium border-slate-300">
              Войти
            </Button>
          </Link>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// FOOTER
// ---------------------------------------------------------------------------

function Footer() {
  const links = [
    { label: 'Возможности', href: '#features' },
    { label: 'Как это работает', href: '#how-it-works' },
    { label: 'Для отеля', href: '#for-hotels' },
    { label: 'Войти', href: '/login' },
  ]
  return (
    <footer className="bg-slate-900 py-10 px-6 border-t border-white/10">
      <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-5">
        <div className="flex flex-col items-center md:items-start gap-1">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-gradient-to-br from-[#2461FF] to-[#7C3AED] rounded-md flex items-center justify-center">
              <Hotel className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-white font-bold">OmniOS</span>
          </div>
          <p className="text-slate-500 text-xs mt-1">CRM для отелей с ИИ-агентом</p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-5">
          {links.map(link => (
            <a key={link.label} href={link.href} className="text-sm text-slate-500 hover:text-slate-300 transition-colors">
              {link.label}
            </a>
          ))}
        </div>
        <p className="text-slate-500 text-sm">© 2026 OmniOS</p>
      </div>
      <div className="max-w-5xl mx-auto flex items-center justify-center gap-2 mt-8 pt-6 border-t border-white/10">
        <span className="text-slate-600 text-xs">Разработано командой</span>
        <span className="text-white text-xs font-semibold">Axon</span>
      </div>
    </footer>
  )
}
