import { createFileRoute, useNavigate, Link } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2Icon, BuildingIcon, UserIcon, LockIcon, MailIcon, ArrowLeftIcon, Sparkles } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { useAuth } from '@/contexts/auth-context'
import { register as registerApi, ApiError } from '@/lib/api'

export const Route = createFileRoute('/register')({
  component: RegisterPage,
})

const schema = z.object({
  name: z.string().min(1, 'Имя обязательно'),
  email: z.string().email('Некорректный email'),
  password: z.string().min(8, 'Пароль должен содержать минимум 8 символов'),
  organization_name: z.string().min(1, 'Название организации обязательно'),
})
type FormData = z.infer<typeof schema>

function FloatingOrb({ className, delay = 0 }: { className: string; delay?: number }) {
  return (
    <div
      className={`absolute rounded-full blur-3xl opacity-[0.15] animate-pulse ${className}`}
      style={{ animationDelay: `${delay}s`, animationDuration: '6s' }}
    />
  )
}

function RegisterPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [serverError, setServerError] = useState<string | null>(null)
  const [mounted, setMounted] = useState(false)
  const [focusedField, setFocusedField] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 50)
    return () => clearTimeout(timer)
  }, [])

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', email: '', password: '', organization_name: '' },
  })

  const onSubmit = async (data: FormData) => {
    setServerError(null)
    try {
      await registerApi({
        email: data.email,
        password: data.password,
        name: data.name,
        organization_name: data.organization_name,
      })
      await login(data.email, data.password)
      navigate({ to: '/dashboard' })
    } catch (err) {
      if (err instanceof ApiError && err.data) {
        const d = err.data as Record<string, string>
        if (d.email) form.setError('email', { message: d.email })
        if (d.password) form.setError('password', { message: d.password })
        if (d.organization_name) form.setError('organization_name', { message: d.organization_name })
        if (d.non_field_errors) setServerError(d.non_field_errors)
      } else {
        setServerError('Что-то пошло не так. Попробуйте ещё раз.')
      }
    }
  }

  const fields = [
    { name: 'name' as const, label: 'Полное имя', placeholder: 'Иван Иванов', icon: UserIcon, type: 'text' },
    { name: 'email' as const, label: 'Email', placeholder: 'you@company.com', icon: MailIcon, type: 'email' },
    { name: 'password' as const, label: 'Пароль', placeholder: 'Мин. 8 символов', icon: LockIcon, type: 'password' },
    { name: 'organization_name' as const, label: 'Компания / Название рабочего пространства', placeholder: 'ООО «Акме»', icon: BuildingIcon, type: 'text' },
  ]

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-[#F8FAFF] p-4">
      {/* Animated background orbs matching the landing page theme */}
      <FloatingOrb className="h-96 w-96 bg-[#2461FF] -top-20 -left-20" delay={0} />
      <FloatingOrb className="h-80 w-80 bg-[#7C3AED] top-1/3 -right-20" delay={1.5} />
      <FloatingOrb className="h-64 w-64 bg-[#2461FF] bottom-10 left-1/4" delay={0.8} />
      <FloatingOrb className="h-48 w-48 bg-[#7C3AED] top-10 right-1/3" delay={2.2} />

      {/* Grid pattern overlay */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `linear-gradient(rgba(10,22,40,0.1) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(10,22,40,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />

      {/* Floating particles */}
      {[...Array(6)].map((_, i) => (
        <div
          key={i}
          className={`absolute h-1.5 w-1.5 rounded-full opacity-40 ${i % 2 === 0 ? 'bg-[#2461FF]' : 'bg-[#7C3AED]'}`}
          style={{
            left: `${15 + i * 15}%`,
            top: `${20 + (i % 3) * 25}%`,
            animation: `float ${3 + i * 0.5}s ease-in-out infinite alternate`,
            animationDelay: `${i * 0.4}s`,
          }}
        />
      ))}

      {/* Main card */}
      <div
        className="relative z-10 w-full max-w-md"
        style={{
          opacity: mounted ? 1 : 0,
          transform: mounted ? 'translateY(0) scale(1)' : 'translateY(24px) scale(0.97)',
          transition: 'opacity 0.6s ease, transform 0.6s ease',
        }}
      >
        {/* Logo & header */}
        <div className="mb-8 text-center">
          <div
            className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl shadow-xl"
            style={{
              background: 'linear-gradient(135deg, #2461FF, #7C3AED)',
              boxShadow: '0 8px 30px rgba(36, 97, 255, 0.3)',
            }}
          >
            <Sparkles className="h-8 w-8 text-white" />
          </div>
          <h1
            className="text-3xl font-bold text-slate-900"
            style={{
              fontFamily: "'Ubuntu', sans-serif",
              opacity: mounted ? 1 : 0,
              transform: mounted ? 'translateY(0)' : 'translateY(10px)',
              transition: 'opacity 0.6s ease 0.1s, transform 0.6s ease 0.1s',
            }}
          >
            Создать аккаунт
          </h1>
          <p
            className="mt-2 text-slate-500"
            style={{
              opacity: mounted ? 1 : 0,
              transition: 'opacity 0.6s ease 0.2s',
            }}
          >
            Бесплатно · Без банковской карты
          </p>
        </div>

        {/* Glass card */}
        <div
          className="rounded-2xl p-8"
          style={{
            background: 'rgba(255, 255, 255, 0.75)',
            backdropFilter: 'blur(24px)',
            border: '1px solid rgba(255, 255, 255, 0.6)',
            boxShadow: '0 20px 40px rgba(10, 22, 40, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.8)',
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(16px)',
            transition: 'opacity 0.6s ease 0.15s, transform 0.6s ease 0.15s',
          }}
        >
          {serverError ? (
            <div
              className="mb-5 rounded-xl p-4 text-sm text-red-600"
              style={{
                background: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.15)',
                animation: 'shake 0.4s ease',
              }}
            >
              {serverError}
            </div>
          ) : null}

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
              {fields.map(({ name, label, placeholder, icon: Icon, type }, idx) => (
                <FormField
                  key={name}
                  control={form.control}
                  name={name}
                  render={({ field }) => (
                    <FormItem
                      style={{
                        opacity: mounted ? 1 : 0,
                        transform: mounted ? 'translateY(0)' : 'translateY(10px)',
                        transition: `opacity 0.5s ease ${0.2 + idx * 0.07}s, transform 0.5s ease ${0.2 + idx * 0.07}s`,
                      }}
                    >
                      <FormLabel className="text-sm font-medium text-slate-700">{label}</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Icon
                            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 transition-colors duration-200"
                            style={{ color: focusedField === name ? '#2461FF' : '#94a3b8' }}
                          />
                          <Input
                            {...field}
                            type={type}
                            placeholder={placeholder}
                            className="pl-10 h-11 transition-all duration-200"
                            style={{
                              background: 'rgba(255, 255, 255, 0.8)',
                              border: focusedField === name
                                ? '1px solid rgba(36, 97, 255, 0.6)'
                                : '1px solid rgba(0, 0, 0, 0.08)',
                              color: '#0f172a',
                              boxShadow: focusedField === name
                                ? '0 0 0 3px rgba(36, 97, 255, 0.12)'
                                : 'none',
                            }}
                            onFocus={() => setFocusedField(name)}
                            onBlur={() => {
                              field.onBlur()
                              setFocusedField(null)
                            }}
                          />
                        </div>
                      </FormControl>
                      <FormMessage className="text-red-500 text-xs" />
                    </FormItem>
                  )}
                />
              ))}

              <button
                type="submit"
                disabled={form.formState.isSubmitting}
                className="relative w-full h-11 rounded-xl font-semibold text-white overflow-hidden transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed mt-2 shimmer-btn"
                style={{
                  background: 'linear-gradient(135deg, #2461FF, #7C3AED)',
                  boxShadow: form.formState.isSubmitting ? 'none' : '0 4px 20px rgba(36, 97, 255, 0.25)',
                  transform: form.formState.isSubmitting ? 'scale(0.99)' : 'scale(1)',
                }}
                onMouseEnter={e => {
                  if (!form.formState.isSubmitting) {
                    (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 6px 28px rgba(36, 97, 255, 0.4)'
                    ;(e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-1px)'
                  }
                }}
                onMouseLeave={e => {
                  if (!form.formState.isSubmitting) {
                    (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 20px rgba(36, 97, 255, 0.25)'
                    ;(e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)'
                  }
                }}
              >
                {form.formState.isSubmitting ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2Icon className="h-4 w-4 animate-spin" />
                    Создание аккаунта...
                  </span>
                ) : (
                  'Создать бесплатный аккаунт'
                )}
              </button>
            </form>
          </Form>
        </div>

        {/* Footer links */}
        <div
          className="mt-6 flex flex-col items-center gap-3"
          style={{
            opacity: mounted ? 1 : 0,
            transition: 'opacity 0.6s ease 0.4s',
          }}
        >
          <p className="text-sm text-slate-500">
            Уже есть аккаунт?{' '}
            <Link to="/login" className="font-semibold text-[#2461FF] transition-colors hover:text-[#7C3AED]">
              Войти
            </Link>
          </p>
          <Link
            to="/"
            className="flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-slate-800"
          >
            <ArrowLeftIcon className="h-3.5 w-3.5" />
            На главную
          </Link>
        </div>
      </div>

      <style>{`
        @keyframes float {
          from { transform: translateY(0px); }
          to { transform: translateY(-12px); }
        }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-6px); }
          40% { transform: translateX(6px); }
          60% { transform: translateX(-4px); }
          80% { transform: translateX(4px); }
        }
      `}</style>
    </div>
  )
}
