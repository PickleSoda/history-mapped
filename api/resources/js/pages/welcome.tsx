import { Head, Link, usePage } from '@inertiajs/react';
import { dashboard, login, register } from '@/routes';

export default function Welcome({
    canRegister = true,
}: {
    canRegister?: boolean;
}) {
    const { auth } = usePage().props;

    return (
        <>
            <Head title="Welcome" />
            <div className="flex min-h-screen flex-col items-center bg-[#FDFDFC] p-6 text-[#1b1b18] lg:justify-center lg:p-8 dark:bg-[#0a0a0a]">
                <header className="mb-6 w-full max-w-4xl text-sm">
                    <nav className="flex items-center justify-end gap-4">
                        {auth.user ? (
                            <Link
                                href={dashboard()}
                                className="inline-block rounded-sm border border-[#19140035] px-5 py-1.5 text-sm leading-normal hover:border-[#1915014a] dark:border-[#3E3E3A] dark:text-[#EDEDEC] dark:hover:border-[#62605b]"
                            >
                                Dashboard
                            </Link>
                        ) : (
                            <>
                                <Link
                                    href={login()}
                                    className="inline-block rounded-sm border border-transparent px-5 py-1.5 text-sm leading-normal hover:border-[#19140035] dark:text-[#EDEDEC] dark:hover:border-[#3E3E3A]"
                                >
                                    Log in
                                </Link>
                                {canRegister && (
                                    <Link
                                        href={register()}
                                        className="inline-block rounded-sm border border-[#19140035] px-5 py-1.5 text-sm leading-normal hover:border-[#1915014a] dark:border-[#3E3E3A] dark:text-[#EDEDEC] dark:hover:border-[#62605b]"
                                    >
                                        Register
                                    </Link>
                                )}
                            </>
                        )}
                    </nav>
                </header>
                <div className="flex w-full items-center justify-center lg:grow">
                    <main className="flex w-full max-w-xl flex-col items-center gap-4 rounded-lg bg-white p-10 text-center shadow-[inset_0px_0px_0px_1px_rgba(26,26,0,0.16)] dark:bg-[#161615] dark:text-[#EDEDEC] dark:shadow-[inset_0px_0px_0px_1px_#fffaed2d]">
                        <h1 className="text-2xl font-semibold tracking-tight">
                            History Mapped
                        </h1>
                        <p className="text-[#706f6c] dark:text-[#A1A09A]">
                            An interactive historical atlas.
                        </p>
                        <div className="mt-2 flex gap-4 text-sm">
                            <a
                                href="https://github.com/PickleSoda/history-mapped"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline underline-offset-4 hover:text-[#1b1b18] dark:hover:text-white"
                            >
                                Repository
                            </a>
                            <a
                                href="https://github.com/PickleSoda/history-mapped/tree/develop/docs"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline underline-offset-4 hover:text-[#1b1b18] dark:hover:text-white"
                            >
                                Documentation
                            </a>
                        </div>
                    </main>
                </div>
            </div>
        </>
    );
}
