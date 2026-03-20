<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\CalendarSystem;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class CalendarSystemController extends Controller
{
    /**
     * Display the calendar systems listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $calendars = CalendarSystem::query()
            ->when($search, fn ($q) => $q->where('name', 'ilike', "%{$search}%")
                ->orWhere('code', 'ilike', "%{$search}%"))
            ->orderBy('name')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/calendar-systems', [
            'calendars' => $calendars->through(fn (CalendarSystem $calendar) => [
                'calendar_id' => $calendar->calendar_id,
                'name' => $calendar->name,
                'code' => $calendar->code,
                'calendar_type' => $calendar->calendar_type,
                'epoch_gregorian' => $calendar->epoch_gregorian,
                'still_in_use' => $calendar->still_in_use,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
