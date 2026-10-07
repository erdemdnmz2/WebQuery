import React from 'react';
import { BrandMark } from './BrandMark';

export interface AuthLayoutProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}

/**
 * Two-column sign-in frame. The left column carries the form; the right
 * column states what the product actually does, which is more useful to a
 * new operator than a decorative gradient.
 */
export const AuthLayout: React.FC<AuthLayoutProps> = ({ title, subtitle, children, footer }) => (
  <div className="grid min-h-dvh grid-cols-1 lg:grid-cols-[minmax(0,460px)_1fr]">
    <main className="flex flex-col justify-center px-6 py-12 sm:px-12">
      <div className="mx-auto w-full max-w-sm animate-enter">
        <div className="mb-9 flex items-center gap-2.5">
          <BrandMark className="text-accent" size={22} />
          <span className="text-[15px] font-medium tracking-tight text-fg">WebQuery</span>
        </div>

        <h1 className="text-[26px] font-medium leading-tight tracking-tight text-fg">{title}</h1>
        <p className="mt-2 text-[13.5px] leading-relaxed text-subtle">{subtitle}</p>

        <div className="mt-8">{children}</div>

        <div className="mt-7 border-t border-line pt-5 text-[13px] text-subtle">{footer}</div>
      </div>
    </main>

    <aside className="hidden flex-col justify-center border-l border-line bg-sunken px-12 py-12 lg:flex xl:px-16">
      <div className="max-w-md">
        <p className="text-[21px] font-medium leading-snug tracking-tight text-fg">
          Üretim veritabanlarına giden her sorgu kayıt altında.
        </p>

        <dl className="mt-8 flex flex-col divide-y divide-line border-y border-line">
          {[
            {
              term: 'Risk analizi',
              detail:
                'Yazdığınız SQL çalıştırılmadan önce sınıflandırılır. Şema değiştiren veya toplu veri silen ifadeler yönetici onayına düşer.',
            },
            {
              term: 'Maskeleme',
              detail:
                'Yönetici tarafından işaretlenen kolonlar sonuç setine hiç girmez. Geçici kurallarınızı kendiniz de ekleyebilirsiniz.',
            },
            {
              term: 'Denetim izi',
              detail: 'Her çalıştırma; kullanıcı, sunucu, veritabanı ve sorgu metniyle birlikte saklanır.',
            },
          ].map((item) => (
            <div key={item.term} className="py-4">
              <dt className="text-[13px] font-medium text-fg">{item.term}</dt>
              <dd className="mt-1 text-[13px] leading-relaxed text-subtle">{item.detail}</dd>
            </div>
          ))}
        </dl>

        <p className="mt-6 text-[12.5px] text-subtle">Erişiminiz yoksa veritabanı yöneticinizle görüşün.</p>
      </div>
    </aside>
  </div>
);
